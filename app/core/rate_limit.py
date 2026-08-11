from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings


def default_rate_limit() -> str:
    return f"{get_settings().rate_limit_default_per_minute}/minute"


def auth_rate_limit() -> str:
    return f"{get_settings().rate_limit_auth_per_minute}/minute"


limiter = Limiter(key_func=get_remote_address, default_limits=[default_rate_limit])
