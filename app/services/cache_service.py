import json
import logging
import time

import redis

from app.config import get_settings

logger = logging.getLogger(__name__)

_BACKOFF_SECONDS = 60
_connection_failed_until: float = 0


class CacheService:
    _client = None

    @classmethod
    def _is_cache_available(cls) -> bool:
        return time.time() > _connection_failed_until

    @classmethod
    def _mark_connection_failed(cls) -> None:
        global _connection_failed_until
        _connection_failed_until = time.time() + _BACKOFF_SECONDS

    @classmethod
    def _get_client(cls):
        """Initializes and returns the Redis client with graceful failure handling."""
        if not cls._is_cache_available():
            return None

        if cls._client is None:
            settings = get_settings()
            if not settings.redis_url:
                cls._mark_connection_failed()
                return None

            try:
                cls._client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=0.3,
                    socket_connect_timeout=0.3,
                )
                cls._client.ping()
                logger.info("Connected to Redis successfully for caching.")
            except Exception as e:
                logger.warning("Could not connect to Redis: %s. Falling back to PostgreSQL-only mode.", e)
                cls._client = None
                cls._mark_connection_failed()

        return cls._client

    @classmethod
    def get_cached_candidates(cls, swiper_id: int, event_id: int) -> list[int] | None:
        client = cls._get_client()
        if not client:
            return None

        key = f"candidates:{swiper_id}:{event_id}"
        try:
            data = client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error("Redis get error: %s", e)
        return None

    @classmethod
    def set_cached_candidates(cls, swiper_id: int, event_id: int, candidate_ids: list[int], ttl: int = 3600) -> None:
        client = cls._get_client()
        if not client:
            return

        key = f"candidates:{swiper_id}:{event_id}"
        try:
            client.setex(key, ttl, json.dumps(candidate_ids))
        except Exception as e:
            logger.error("Redis setex error: %s", e)

    @classmethod
    def remove_swiped_candidate(cls, swiper_id: int, event_id: int, target_id: int) -> None:
        client = cls._get_client()
        if not client:
            return

        key = f"candidates:{swiper_id}:{event_id}"
        try:
            # NOTE: Non-atomic read-modify-write. Under high concurrency, two
            # simultaneous swipes could cause one removal to be lost.
            # For production scale, replace with Redis LREM on a list type.
            cached_ids = cls.get_cached_candidates(swiper_id, event_id)
            if cached_ids and target_id in cached_ids:
                cached_ids.remove(target_id)
                cls.set_cached_candidates(swiper_id, event_id, cached_ids)
        except Exception as e:
            logger.error("Redis remove list item error: %s", e)

    @classmethod
    def clear_candidates_cache(cls, swiper_id: int, event_id: int) -> None:
        client = cls._get_client()
        if not client:
            return

        key = f"candidates:{swiper_id}:{event_id}"
        try:
            client.delete(key)
        except Exception as e:
            logger.error("Redis delete error: %s", e)
