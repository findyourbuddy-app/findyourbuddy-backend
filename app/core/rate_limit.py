from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings


def get_real_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


def default_rate_limit() -> str:
    return f"{get_settings().rate_limit_default_per_minute}/minute"


def auth_rate_limit() -> str:
    return f"{get_settings().rate_limit_auth_per_minute}/minute"


def messages_rate_limit() -> str:
    return f"{get_settings().rate_limit_messages_per_minute}/minute"


def event_writes_rate_limit() -> str:
    return f"{get_settings().rate_limit_event_writes_per_minute}/minute"


def ai_rate_limit() -> str:
    # Each call is a real, billed OpenAI request (vision or LLM) -- much
    # tighter than the general default so one abusive client can't run up
    # the API bill.
    return f"{get_settings().rate_limit_ai_per_minute}/minute"


def _limiter_kwargs() -> dict:
    storage_uri = get_settings().rate_limit_storage_uri
    return {"storage_uri": storage_uri} if storage_uri else {}


limiter = Limiter(
    key_func=get_real_client_ip,
    default_limits=[default_rate_limit],
    **_limiter_kwargs(),
)
