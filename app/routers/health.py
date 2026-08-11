from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
def check_service_status() -> dict[str, str]:
    return {"status": "ok"}
