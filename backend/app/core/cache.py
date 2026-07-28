from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


async def invalidate_score_cache(redis: Redis, user_id: str) -> None:
    """Evict every cached score for this user regardless of model version or
    feature bucket -- a fresh ledger/chama write should never be served a
    stale cached score, TTL be damned (see scoring engine notes)."""
    async for key in redis.scan_iter(match=f"score:{user_id}:*"):
        await redis.delete(key)
