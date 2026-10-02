"""Redis connection for cached alert views and pipeline job status.

Every helper fails soft: when Redis is not configured or unreachable the API
simply serves uncached reads.
"""

from __future__ import annotations

import json
from typing import Any

import redis

from app.core.config import settings

CACHE_PREFIX = "bitcraft:cache:"
STATUS_KEY = "bitcraft:pipeline:status"

redis_client: redis.Redis | None = (
    redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.3,
        socket_timeout=0.3,
    )
    if settings.redis_url
    else None
)


def cache_get(key: str) -> Any | None:
    """Cached JSON value, or None on miss / no Redis."""
    if redis_client is None:
        return None
    try:
        raw = redis_client.get(CACHE_PREFIX + key)
    except redis.RedisError:
        return None
    return json.loads(raw) if raw else None


def cache_set(key: str, value: Any, ttl_s: int | None = None) -> None:
    """Store a JSON value with a TTL (best effort)."""
    if redis_client is None:
        return
    try:
        redis_client.set(CACHE_PREFIX + key, json.dumps(value), ex=ttl_s or settings.cache_ttl_s)
    except redis.RedisError:
        pass


def cache_clear() -> None:
    """Drop every cached view (after a reload)."""
    if redis_client is None:
        return
    try:
        for key in redis_client.scan_iter(CACHE_PREFIX + "*"):
            redis_client.delete(key)
    except redis.RedisError:
        pass


def get_raw(key: str) -> str | None:
    """Plain GET for non-cache keys (pipeline status)."""
    if redis_client is None:
        return None
    try:
        return redis_client.get(key)
    except redis.RedisError:
        return None


def set_raw(key: str, value: str) -> None:
    """Plain SET for non-cache keys (best effort)."""
    if redis_client is None:
        return
    try:
        redis_client.set(key, value)
    except redis.RedisError:
        pass
