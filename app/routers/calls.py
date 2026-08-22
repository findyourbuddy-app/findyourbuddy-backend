from fastapi import APIRouter, Depends

from app.config import get_settings
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("/ice-servers")
def get_ice_servers(current_user: User = Depends(get_current_user)) -> dict:
    """Returns ICE server config (STUN + TURN) for WebRTC peer connections."""
    settings = get_settings()
    servers: list[dict] = [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
    ]
    for url in settings.turn_urls:
        servers.append({
            "urls": url,
            "username": settings.turn_username,
            "credential": settings.turn_credential,
        })
    return {"ice_servers": servers}
