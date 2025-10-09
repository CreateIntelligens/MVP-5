"""
Redis 客戶端配置
"""
import redis
import os
import logging

logger = logging.getLogger(__name__)

# Redis 連接配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 創建 Redis 客戶端 (連接池配置)
redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    max_connections=10000,  # 允許最高 1 萬個連線
    socket_connect_timeout=30,  # 提高連接超時
    socket_timeout=120,  # 提高讀寫超時到 2 分鐘
    socket_keepalive=True,  # 啟用 keepalive
    socket_keepalive_options={},
    retry_on_timeout=True,
    retry_on_error=[redis.exceptions.ConnectionError, redis.exceptions.TimeoutError],
    health_check_interval=30  # 每 30 秒檢查連接健康
)

# 延遲測試連接 (避免 import 時阻塞)
def test_redis_connection():
    """測試 Redis 連接"""
    try:
        redis_client.ping()
        logger.info(f"Redis 連接成功: {REDIS_URL}")
        return True
    except Exception as e:
        logger.error(f"Redis 連接失敗: {e}")
        return False

# Redis Key 前綴
TASK_KEY_PREFIX = "task:"
QUEUE_SIZE_KEY = "queue_size"
GPU_LOCK_KEY = "gpu_lock"
