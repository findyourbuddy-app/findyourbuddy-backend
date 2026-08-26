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

    # Atomically removes target_id from the JSON array stored at key.
    # Uses a Lua script so the read-modify-write happens in a single Redis command.
    _REMOVE_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then return 0 end
local ttl = redis.call('TTL', KEYS[1])
local ids = cjson.decode(raw)
local new_ids = {}
for _, v in ipairs(ids) do
    if v ~= tonumber(ARGV[1]) then
        table.insert(new_ids, v)
    end
end
if ttl > 0 then
    redis.call('SETEX', KEYS[1], ttl, cjson.encode(new_ids))
else
    redis.call('SET', KEYS[1], cjson.encode(new_ids))
end
return 1
"""

    @classmethod
    def remove_swiped_candidate(cls, swiper_id: int, event_id: int, target_id: int) -> None:
        client = cls._get_client()
        if not client:
            return

        key = f"candidates:{swiper_id}:{event_id}"
        try:
            client.eval(cls._REMOVE_SCRIPT, 1, key, target_id)
        except Exception as e:
            logger.error("Redis atomic remove error: %s", e)

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

    @classmethod
    def get_cached_icebreakers(cls, user_a_id: int, user_b_id: int) -> list[dict] | None:
        client = cls._get_client()
        if not client:
            return None

        lo, hi = (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)
        key = f"icebreakers:{lo}:{hi}"
        try:
            data = client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error("Redis icebreaker get error: %s", e)
        return None

    @classmethod
    def set_cached_icebreakers(
        cls, user_a_id: int, user_b_id: int, items: list[dict], ttl: int = 86400
    ) -> None:
        client = cls._get_client()
        if not client:
            return

        lo, hi = (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)
        key = f"icebreakers:{lo}:{hi}"
        try:
            client.setex(key, ttl, json.dumps(items))
        except Exception as e:
            logger.error("Redis icebreaker set error: %s", e)
