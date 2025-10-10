"""
Redis 分散式鎖實現
"""
import asyncio
import uuid
import logging
from core.redis_client import redis_client, GPU_LOCK_KEY

logger = logging.getLogger(__name__)


class RedisLock:
    """Redis 分散式鎖 (用於 GPU 串行處理) - 使用 Pub/Sub 避免輪詢"""

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
        self.channel = f"{key}:channel"

    async def acquire(self):
        """獲取鎖 (使用 exponential backoff 降低 Redis 壓力)"""
        backoff = 0.01  # 從 10ms 開始
        max_backoff = 1.0  # 最大 1 秒

        while True:
            # SET key value NX EX timeout
            acquired = await redis_client.set(
                self.key,
                self.identifier,
                nx=True,
                ex=self.timeout
            )
            if acquired:
                logger.debug(f"獲取鎖成功: {self.key} ({self.identifier})")
                return True

            # 使用 exponential backoff 等待
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, max_backoff)

    async def release(self):
        """釋放鎖 (使用 Lua script 保證原子性) 並通知等待者"""
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            redis.call("del", KEYS[1])
            redis.call("publish", KEYS[2], "released")
            return 1
        else
            return 0
        end
        """
        result = await redis_client.eval(
            lua_script,
            2,
            self.key,
            self.channel,
            self.identifier
        )
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
