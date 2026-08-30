import base64
import hashlib
import hmac
import time

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/calls", tags=["calls"])

_STUN_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
]


def _turn_credentials(settings: Settings, user_id: int) -> tuple[str, str]:
    """Short-lived HMAC credential (coturn use-auth-secret) when a secret is
    configured, otherwise the static username/credential pair."""
    if not settings.turn_static_auth_secret:
        return settings.turn_username, settings.turn_credential

    expiry = int(time.time()) + settings.turn_credential_ttl_seconds
    username = f"{expiry}:{user_id}"
    digest = hmac.new(
        settings.turn_static_auth_secret.encode(), username.encode(), hashlib.sha1
    ).digest()
    return username, base64.b64encode(digest).decode()


@router.get("/ice-servers")
def get_ice_servers(current_user: User = Depends(get_current_user)) -> dict:
    """Returns ICE server config (STUN + TURN) for WebRTC peer connections."""
    settings = get_settings()
    servers: list[dict] = list(_STUN_SERVERS)

    if settings.turn_urls:
        username, credential = _turn_credentials(settings, current_user.id)
        for url in settings.turn_urls:
            servers.append({"urls": url, "username": username, "credential": credential})

    return {"ice_servers": servers}
