"""
Redis 客戶端配置
"""
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
