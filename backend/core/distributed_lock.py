"""
Redis 分散式鎖實現
"""
import asyncio
import uuid
import logging
from core.redis_client import redis_client, GPU_LOCK_KEY

logger = logging.getLogger(__name__)


class RedisLock:
    """Redis 分散式鎖 (用於 GPU 串行處理)"""

    def __init__(self, key: str = GPU_LOCK_KEY, timeout: int = 1800):
        """
        初始化分散式鎖

        Args:
            key: Redis key 名稱
            timeout: 鎖超時時間 (秒) - 30 分鐘避免死鎖
        """
        self.key = key
        self.timeout = timeout
        self.identifier = str(uuid.uuid4())  # 唯一標識

    async def acquire(self):
        """獲取鎖 (阻塞直到成功)"""
        while True:
            # SET key value NX EX timeout
            if redis_client.set(self.key, self.identifier, nx=True, ex=self.timeout):
                logger.debug(f"獲取鎖成功: {self.key} ({self.identifier})")
                return True
            # 沒拿到鎖,等待 50ms 後重試
            await asyncio.sleep(0.05)

    async def release(self):
        """釋放鎖 (使用 Lua script 保證原子性)"""
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = redis_client.eval(lua_script, 1, self.key, self.identifier)
        if result:
            logger.debug(f"釋放鎖成功: {self.key} ({self.identifier})")
        else:
            logger.warning(f"釋放鎖失敗 (可能已被其他進程釋放或超時): {self.key}")

    async def __aenter__(self):
        """Context manager 進入時獲取鎖"""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager 退出時釋放鎖"""
        await self.release()
