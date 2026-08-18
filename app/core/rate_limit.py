from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings


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


limiter = Limiter(key_func=get_remote_address, default_limits=[default_rate_limit])
