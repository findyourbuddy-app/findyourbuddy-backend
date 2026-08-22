import json
import logging
import os
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_staff_user
from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)
from app.schemas.admin import UserActiveStatusUpdate
from app.schemas.subscription import GrantPremiumRequest, SubscriptionStatus
from app.schemas.user import UserRead
from app.services.admin_service import UserNotFoundError, list_users, set_user_active_status
from app.services.subscription_service import get_subscription, grant_premium, is_premium, revoke_premium

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserRead])
def list_all_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
) -> list[User]:
    return list_users(db, skip=skip, limit=limit)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user_active_status(
    user_id: int,
    data: UserActiveStatusUpdate,
    _staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
) -> User:
    try:
        result = set_user_active_status(db, user_id, data.is_active)
        action = "activated" if data.is_active else "suspended"
        logger.info("admin_action action=%s target_user_id=%s actor_id=%s", action, user_id, _staff_user.id)
        return result
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc


@router.post("/users/{user_id}/premium", response_model=SubscriptionStatus)
def grant_user_premium(
    user_id: int,
    data: GrantPremiumRequest,
    _staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
) -> SubscriptionStatus:
    grant_premium(db, user_id, expires_at=data.expires_at)
    logger.info("admin_action action=grant_premium target_user_id=%s expires_at=%s actor_id=%s", user_id, data.expires_at, _staff_user.id)
    return SubscriptionStatus(is_premium=is_premium(db, user_id), expires_at=data.expires_at)


@router.delete("/users/{user_id}/premium", response_model=SubscriptionStatus)
def revoke_user_premium(
    user_id: int,
    _staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
) -> SubscriptionStatus:
    revoke_premium(db, user_id)
    logger.info("admin_action action=revoke_premium target_user_id=%s actor_id=%s", user_id, _staff_user.id)
    subscription = get_subscription(db, user_id)
    return SubscriptionStatus(
        is_premium=is_premium(db, user_id),
        expires_at=subscription.expires_at if subscription else None,
    )


@router.get("/logs", response_class=HTMLResponse)
def get_logs(
    _staff_user: User = Depends(get_current_staff_user)
):
    """Renders the last 200 system log statements in a clean dark-themed dashboard."""
    log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app.log")
    if not os.path.exists(log_file):
        return "<html><body style='background:#121214; color:#fff; text-align:center; padding-top:100px;'><h1>No logs found yet.</h1></body></html>"

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        parsed_logs = []
        for line in reversed(lines[-200:]):
            try:
                parsed_logs.append(json.loads(line))
            except Exception:
                parsed_logs.append({"timestamp": "", "level": "UNKNOWN", "logger": "root", "message": line})

        rows = ""
        for log in parsed_logs:
            level = escape(log.get("level", "INFO"))
            color = "#ff4d4d" if level in ("ERROR", "CRITICAL") else "#ffaa00" if level == "WARNING" else "#2eb82e" if level == "INFO" else "#8c8c96"
            timestamp = escape(str(log.get("timestamp", "")))
            logger_name = escape(str(log.get("logger", "")))
            message = escape(str(log.get("message", "")))
            rows += f"""
                <tr style="border-bottom: 1px solid #2e2e36;">
                    <td style="padding: 10px; color: #8c8c96; white-space: nowrap;">{timestamp}</td>
                    <td style="padding: 10px;"><span style="color: {color}; font-weight: bold; font-size: 11px; border: 1px solid {color}; padding: 2px 6px; border-radius: 4px;">{level}</span></td>
                    <td style="padding: 10px; color: #9b7bff;">{logger_name}</td>
                    <td style="padding: 10px; word-break: break-all;">{message}</td>
                </tr>
            """
            
        html = f"""
            <html>
                <head>
                    <meta charset="utf-8">
                    <title>FindYourBuddy Server Logs</title>
                </head>
                <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #121214; color: #ffffff; padding: 20px;">
                    <div style="max-width: 1200px; margin: 0 auto;">
                        <h1 style="border-bottom: 2px solid #2e2e36; padding-bottom: 15px; display: flex; justify-content: space-between; align-items: center;">
                            <span>📋 FindYourBuddy Sistem Logları</span>
                            <span style="font-size: 14px; background: #2a2a30; padding: 6px 12px; border-radius: 6px; color: #c9c9cf;">Son 200 Kayıt</span>
                        </h1>
                        <table style="width: 100%; border-collapse: collapse; background: #1a1a1e; border-radius: 8px; overflow: hidden; margin-top: 20px;">
                            <thead>
                                <tr style="background: #232329; text-align: left; border-bottom: 2px solid #2e2e36; color: #8c8c96; font-size: 14px;">
                                    <th style="padding: 12px; width: 180px;">Zaman</th>
                                    <th style="padding: 12px; width: 100px;">Seviye</th>
                                    <th style="padding: 12px; width: 150px;">Logger</th>
                                    <th style="padding: 12px;">Mesaj</th>
                                </tr>
                            </thead>
                            <tbody style="font-size: 13px; line-height: 1.5;">
                                {rows}
                            </tbody>
                        </table>
                    </div>
                </body>
            </html>
        """
        return html
    except Exception as e:
        return f"<html><body><h1>Error reading logs: {str(e)}</h1></body></html>"
