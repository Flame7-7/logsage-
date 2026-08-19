"""
LogSage AI — Redis Client
Async Redis with pub/sub, queues, and caching helpers.
"""

from typing import Any

import structlog
from redis.asyncio import ConnectionPool, Redis
from redis.asyncio.client import PubSub

from core.config import settings

logger = structlog.get_logger(__name__)

_pool: ConnectionPool | None = None
_client: Redis | None = None


async def get_redis() -> Redis:
    """Return shared async Redis client."""
    global _pool, _client
    if _client is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
        _client = Redis(connection_pool=_pool)
        logger.info("Redis client initialized", url=settings.REDIS_URL)
    return _client


async def close_redis() -> None:
    global _client, _pool
    if _client:
        await _client.close()
        _client = None
    if _pool:
        await _pool.disconnect()
        _pool = None
    logger.info("Redis connection closed")


# ── Queue helpers ─────────────────────────────────────────────────────────────

QUEUE_LOG_INGESTION = "logsage:queue:ingestion"
QUEUE_EMBEDDING = "logsage:queue:embedding"
QUEUE_CLUSTERING = "logsage:queue:clustering"
CHANNEL_LIVE_EVENTS = "logsage:live:events"
CHANNEL_ALERTS = "logsage:alerts"


async def enqueue(queue: str, payload: str) -> int:
    r = await get_redis()
    return await r.rpush(queue, payload)


async def dequeue(queue: str, timeout: int = 5) -> str | None:
    r = await get_redis()
    result = await r.blpop(queue, timeout=timeout)
    if result:
        return result[1]
    return None


async def queue_length(queue: str) -> int:
    r = await get_redis()
    return await r.llen(queue)


async def publish(channel: str, message: str) -> int:
    r = await get_redis()
    return await r.publish(channel, message)


async def get_pubsub() -> PubSub:
    r = await get_redis()
    return r.pubsub()


# ── Cache helpers ─────────────────────────────────────────────────────────────

async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    r = await get_redis()
    await r.setex(key, ttl, str(value))


async def cache_get(key: str) -> str | None:
    r = await get_redis()
    return await r.get(key)


async def cache_delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


# ── Metrics counters ──────────────────────────────────────────────────────────

async def increment_counter(key: str, amount: int = 1) -> int:
    r = await get_redis()
    return await r.incrby(key, amount)


async def get_counter(key: str) -> int:
    r = await get_redis()
    val = await r.get(key)
    return int(val) if val else 0
