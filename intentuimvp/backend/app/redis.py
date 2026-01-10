"""Redis connection pool and client for job queue and caching.

This module provides a singleton Redis connection pool and helper functions
for accessing Redis throughout the application.
"""

from __future__ import annotations

import logging

from redis.asyncio import ConnectionPool, Redis  # type: ignore[import-untyped]
from redis.exceptions import RedisError  # type: ignore[import-untyped]

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global connection pool instance
_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    """Get or create the Redis connection pool.

    The connection pool is created once and reused for all subsequent
    Redis connections. This is more efficient than creating a new
    connection for each operation.

    Returns:
        ConnectionPool: The Redis connection pool.

    Raises:
        RedisError: If the connection pool cannot be created.
    """
    global _pool
    if _pool is None:
        settings = get_settings()
        try:
            _pool = ConnectionPool.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=50,
                socket_keepalive=True,
                socket_keepalive_options={
                    # Enable TCP keepalive
                    1: 1,  # TCP_KEEPIDLE - seconds before sending keepalive probes
                    2: 3,  # TCP_KEEPINTVL - seconds between keepalive probes
                    3: 5,  # TCP_KEEPCNT - number of keepalive probes before dropping
                },
            )
            logger.info(f"Created Redis connection pool: {settings.redis_url}")
        except RedisError as e:
            logger.error(f"Failed to create Redis connection pool: {e}")
            raise
    return _pool


async def get_redis() -> Redis:
    """Get a Redis client from the connection pool.

    This function returns a Redis client that can be used for
    Redis operations. The client is automatically returned to the
    pool when closed.

    Returns:
        Redis: An async Redis client.

    Example:
        >>> redis_client = await get_redis()
        >>> await redis_client.set("key", "value")
        >>> await redis_client.get("key")
        >>> await redis_client.close()
    """
    pool = get_redis_pool()
    return Redis(connection_pool=pool)


async def check_redis_health() -> bool:
    """Check if Redis is accessible and responding.

    This is used by the health check endpoint to verify Redis connectivity.

    Returns:
        bool: True if Redis is accessible, False otherwise.
    """
    try:
        client = await get_redis()
        await client.ping()
        await client.close()
        return True
    except RedisError as e:
        logger.warning(f"Redis health check failed: {e}")
        return False


async def close_redis_pool() -> None:
    """Close the Redis connection pool.

    This should be called on application shutdown to properly close
    all Redis connections.
    """
    global _pool
    if _pool is not None:
        await _pool.aclose()  # type: ignore[attr-defined]
        _pool = None
        logger.info("Closed Redis connection pool")
