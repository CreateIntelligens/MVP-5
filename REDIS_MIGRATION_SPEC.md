# Redis 遷移規格

## 目標
將現有的記憶體狀態管理改為 Redis,支援多 worker 部署,提升 API 響應速度

## 現狀問題
1. 單 worker 處理所有請求 (換臉 + 查詢)
2. Status 查詢會被換臉任務阻塞
3. task_status 字典存在記憶體,重啟後丟失
4. 無法水平擴展

## 改善後效果
1. 4 個 workers 並行接收請求
2. Status 查詢立即回應 (不被 GPU 任務阻塞)
3. 任務狀態持久化到 Redis
4. GPU 處理速度保持不變 (仍然串行 Semaphore 1)

---

## 架構變更

### 1. Docker Compose 新增 Redis 服務

**檔案: `docker-compose.gpu.yml`**

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: ai-face-swap-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  backend:
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/0

volumes:
  redis_data:
```

### 2. Python 依賴更新

**檔案: `backend/requirements.txt`**

新增:
```
redis==5.0.1
```

### 3. Redis 客戶端配置

**新檔案: `backend/core/redis_client.py`**

```python
import redis
import os
import logging

logger = logging.getLogger(__name__)

# Redis 連接配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 創建 Redis 客戶端 (連接池)
redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    max_connections=20,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True
)

# 測試連接
try:
    redis_client.ping()
    logger.info(f"Redis 連接成功: {REDIS_URL}")
except Exception as e:
    logger.error(f"Redis 連接失敗: {e}")
    raise

# Redis Key 前綴
TASK_KEY_PREFIX = "task:"
QUEUE_SIZE_KEY = "queue_size"
GPU_LOCK_KEY = "gpu_lock"
```

### 4. 分散式鎖實現

**新檔案: `backend/core/distributed_lock.py`**

```python
import asyncio
import uuid
from core.redis_client import redis_client, GPU_LOCK_KEY

class RedisLock:
    """Redis 分散式鎖 (用於 GPU 串行處理)"""

    def __init__(self, key: str = GPU_LOCK_KEY, timeout: int = 600):
        self.key = key
        self.timeout = timeout  # 鎖超時時間 (秒)
        self.identifier = str(uuid.uuid4())  # 唯一標識

    async def acquire(self):
        """獲取鎖"""
        while True:
            # SET key value NX EX timeout
            if redis_client.set(self.key, self.identifier, nx=True, ex=self.timeout):
                return True
            # 沒拿到鎖,等待 100ms 後重試
            await asyncio.sleep(0.1)

    async def release(self):
        """釋放鎖 (使用 Lua script 保證原子性)"""
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        redis_client.eval(lua_script, 1, self.key, self.identifier)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()
```

### 5. 任務狀態管理 (Redis 版本)

**修改檔案: `backend/api/face_swap.py`**

```python
import json
from core.redis_client import redis_client, TASK_KEY_PREFIX, QUEUE_SIZE_KEY
from core.distributed_lock import RedisLock

# 移除記憶體變數
# task_status = {}  ❌ 刪除
# processing_semaphore = asyncio.Semaphore(1)  ❌ 刪除
# request_queue_size = 0  ❌ 刪除

MAX_QUEUE_SIZE = 4000

# Redis 工具函數
def get_task_status(task_id: str) -> dict:
    """從 Redis 獲取任務狀態"""
    data = redis_client.get(f"{TASK_KEY_PREFIX}{task_id}")
    if data:
        return json.loads(data)
    return None

def set_task_status(task_id: str, status: dict):
    """設置任務狀態到 Redis (TTL 24小時)"""
    redis_client.setex(
        f"{TASK_KEY_PREFIX}{task_id}",
        86400,  # 24 小時過期
        json.dumps(status, ensure_ascii=False)
    )

def update_task_status(task_id: str, updates: dict):
    """更新任務狀態"""
    task = get_task_status(task_id)
    if task:
        task.update(updates)
        set_task_status(task_id, task)

def get_queue_size() -> int:
    """獲取當前佇列大小"""
    size = redis_client.get(QUEUE_SIZE_KEY)
    return int(size) if size else 0

def incr_queue_size() -> int:
    """佇列大小 +1"""
    return redis_client.incr(QUEUE_SIZE_KEY)

def decr_queue_size() -> int:
    """佇列大小 -1"""
    return redis_client.decr(QUEUE_SIZE_KEY)
```

### 6. 背景任務處理 (使用 Redis 鎖)

**修改: `process_face_swap_task` 函數**

```python
async def process_face_swap_task(
    task_id: str,
    file_content: bytes,
    template_id: str,
    template_content: Optional[bytes] = None,
    source_face_index: int = 0,
    target_face_index: int = 0
):
    """背景任務：執行換臉處理"""

    # 使用 Redis 分散式鎖取代 asyncio.Semaphore
    async with RedisLock():
        incr_queue_size()
        logger.info(f"開始處理背景換臉任務 {task_id}，佇列大小: {get_queue_size()}")

        try:
            # 更新任務狀態
            update_task_status(task_id, {
                "status": "processing",
                "progress": 10,
                "message": "正在初始化 AI 模型..."
            })

            # ... 原有處理邏輯 ...

            # 任務完成
            update_task_status(task_id, {
                "status": "completed",
                "progress": 100,
                "message": "換臉處理完成",
                "result_url": result_url,
                # ...
            })

        except Exception as e:
            # 任務失敗
            update_task_status(task_id, {
                "status": "failed",
                "message": f"換臉處理失敗：{str(e)}",
                "error": str(e)
            })

        finally:
            decr_queue_size()
            logger.info(f"背景換臉任務 {task_id} 完成，佇列大小: {get_queue_size()}")
```

### 7. API Endpoints 更新

**Status 查詢 API:**
```python
@router.get("/face-swap/status/{task_id}")
async def get_task_status_api(task_id: str):
    """查詢任務處理狀態 (從 Redis 讀取,立即回應)"""
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任務不存在")

    return {
        "success": True,
        "task_status": task
    }
```

**佇列狀態 API:**
```python
@router.get("/queue/status")
async def get_queue_status_api():
    """獲取當前佇列狀態"""
    return {
        "success": True,
        "queue_status": {
            "current_queue_size": get_queue_size(),
            "max_queue_size": MAX_QUEUE_SIZE,
            "gpu_lock_exists": redis_client.exists(GPU_LOCK_KEY)
        }
    }
```

### 8. Uvicorn 多 Worker 配置

**修改: `docker-compose.gpu.yml`**

```yaml
backend:
  command: [
    "python", "-m", "uvicorn",
    "app:app",
    "--host", "0.0.0.0",
    "--port", "3001",
    "--workers", "4"  # 4 個 workers
    # 注意: 移除 --reload (不兼容 workers)
  ]
```

---

## 資料結構

### Task Status (Redis Hash)

**Key:** `task:{task_id}`
**TTL:** 86400 秒 (24 小時)
**Value:** JSON 字串

```json
{
  "task_id": "xxx-xxx-xxx",
  "status": "completed",
  "progress": 100,
  "message": "換臉處理完成",
  "result_url": "/results/result_abc123.jpg",
  "original_url": "/uploads/original_abc123.jpg",
  "template_id": "1",
  "template_name": "商務照",
  "template_description": "...",
  "created_at": "2025-10-08T10:00:00",
  "completed_at": "2025-10-08T10:00:15"
}
```

### Queue Size (Redis String)

**Key:** `queue_size`
**Value:** 整數 (當前佇列中的任務數)

### GPU Lock (Redis String)

**Key:** `gpu_lock`
**Value:** UUID (鎖持有者的唯一標識)
**TTL:** 600 秒 (自動過期避免死鎖)

---

## 效能對比

### 現狀 (1 Worker)
- **接收 4000 請求:** ~30-60 秒
- **Status 查詢:** 可能等待數秒 (被換臉任務阻塞)
- **GPU 處理:** 400 張 / 120 秒 = 3.33 張/秒

### Redis + 4 Workers
- **接收 4000 請求:** ~10-20 秒 ✅
- **Status 查詢:** <100ms (立即回應) ✅
- **GPU 處理:** 400 張 / 120 秒 = 3.33 張/秒 (不變)

---

## 遷移步驟

1. ✅ 更新 `docker-compose.gpu.yml` 新增 Redis
2. ✅ 更新 `requirements.txt` 新增 redis
3. ✅ 建立 `core/redis_client.py`
4. ✅ 建立 `core/distributed_lock.py`
5. ✅ 修改 `api/face_swap.py` 使用 Redis
6. ✅ 測試單 worker 模式
7. ✅ 切換到 4 workers
8. ✅ 壓測驗證

---

## 注意事項

1. **Redis 記憶體限制:** 設定 2GB,使用 LRU 淘汰策略
2. **鎖超時:** 600 秒,避免任務卡住導致死鎖
3. **任務 TTL:** 24 小時自動清理舊任務
4. **連接池:** 最大 20 個連接,避免耗盡資源
5. **不能用 --reload:** Workers 模式下不支援自動重載

---

## Rollback 方案

如果 Redis 有問題,可以快速回退:

1. 移除 `depends_on: redis`
2. 改回 `--workers 1 --reload`
3. 恢復原有的記憶體字典版本

---

## 成本
- Redis 容器記憶體: ~100-200MB
- 4 workers vs 1 worker: 記憶體增加 ~1-2GB
- 總共額外記憶體: ~1.5-2.5GB
