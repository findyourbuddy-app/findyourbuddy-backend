import logging
import json
import redis
from app.config import get_settings

logger = logging.getLogger(__name__)

class CacheService:
    _client = None
    _connection_failed = False

    @classmethod
    def _get_client(cls):
        """Initializes and returns the Redis client with graceful failure handling."""
        if cls._connection_failed:
            return None
            
        if cls._client is None:
            settings = get_settings()
            if not settings.redis_url:
                # Redis URL is not configured, silently fall back
                cls._connection_failed = True
                return None
                
            try:
                # Short timeouts + _connection_failed latching below mean an
                # unreachable Redis costs one slow request at most, not a
                # per-request stall -- every call after the first failure
                # skips Redis entirely and goes straight to Postgres.
                cls._client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=0.3,
                    socket_connect_timeout=0.3,
                )
                cls._client.ping()
                logger.info("Connected to Redis successfully for caching.")
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}. Falling back to PostgreSQL-only mode.")
                cls._client = None
                cls._connection_failed = True
                
        return cls._client

    @classmethod
    def get_cached_candidates(cls, swiper_id: int, event_id: int) -> list[int] | None:
        """Retrieves cached candidate user IDs from Redis."""
        client = cls._get_client()
        if not client:
            return None
            
        key = f"candidates:{swiper_id}:{event_id}"
        try:
            data = client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        return None

    @classmethod
    def set_cached_candidates(cls, swiper_id: int, event_id: int, candidate_ids: list[int], ttl=3600) -> None:
        """Caches a list of candidate user IDs in Redis with a time-to-live (default 1 hour)."""
        client = cls._get_client()
        if not client:
            return
            
        key = f"candidates:{swiper_id}:{event_id}"
        try:
            client.setex(key, ttl, json.dumps(candidate_ids))
        except Exception as e:
            logger.error(f"Redis setex error: {e}")

    @classmethod
    def remove_swiped_candidate(cls, swiper_id: int, event_id: int, target_id: int) -> None:
        """Removes a single candidate ID from the cached candidate list in Redis after a swipe action."""
        client = cls._get_client()
        if not client:
            return
            
        key = f"candidates:{swiper_id}:{event_id}"
        try:
            cached_ids = cls.get_cached_candidates(swiper_id, event_id)
            if cached_ids and target_id in cached_ids:
                cached_ids.remove(target_id)
                cls.set_cached_candidates(swiper_id, event_id, cached_ids)
        except Exception as e:
            logger.error(f"Redis remove list item error: {e}")

    @classmethod
    def clear_candidates_cache(cls, swiper_id: int, event_id: int) -> None:
        """Deletes the cached candidate list for a swiper and event."""
        client = cls._get_client()
        if not client:
            return
            
        key = f"candidates:{swiper_id}:{event_id}"
        try:
            client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
