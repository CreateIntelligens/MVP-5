"""
Redis 客戶端配置 (async 版本)
"""
import os
import logging
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Redis 連接配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 建立 async Redis 客戶端 (高併發配置: 支援 4000+ 並發任務)
redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    max_connections=2000,  # 8 workers × 每個可能處理數百個並發任務
    socket_connect_timeout=5,
    socket_timeout=10,  # 減少超時時間，快速釋放連接
    socket_keepalive=True,
    socket_keepalive_options={},
    retry_on_timeout=True,
    retry_on_error=[ConnectionError],
    health_check_interval=30,
)


async def test_redis_connection() -> bool:
    """測試 Redis 連接"""
    try:
        await redis_client.ping()
        logger.info(f"Redis 連接成功: {REDIS_URL}")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Redis 連接失敗: {exc}")
        return False


# Redis Key 前綴
TASK_KEY_PREFIX = "task:"
QUEUE_SIZE_KEY = "queue_size"
GPU_LOCK_KEY = "gpu_lock"
TASK_QUEUE_KEY = "face_swap_queue"
