import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
@router.get("/")
def check_service_status() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/db")
def check_database_status(db: Session = Depends(get_db)) -> JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "error"}
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})


@router.get("/ready")
def check_readiness(db: Session = Depends(get_db)) -> JSONResponse:
    """Deep readiness check — verifies DB connectivity and optional external
    services. Returns 503 if any required dependency is unavailable."""
    checks: dict[str, str] = {}
    healthy = True

    # Database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except SQLAlchemyError as exc:
        logger.error("Readiness check: database unreachable: %s", exc)
        checks["database"] = "error"
        healthy = False

    # Firebase Admin SDK
    try:
        import firebase_admin
        if firebase_admin._apps:
            checks["firebase"] = "ok"
        else:
            checks["firebase"] = "not_initialized"
    except Exception as exc:
        logger.warning("Readiness check: firebase check failed: %s", exc)
        checks["firebase"] = "error"

    http_status = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=http_status, content={"status": "ok" if healthy else "degraded", "checks": checks})
