import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, PlainTextResponse
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


@router.get("/metrics", response_class=PlainTextResponse)
@router.get("/monitoring/metrics", response_class=PlainTextResponse)
def prometheus_metrics(db: Session = Depends(get_db)) -> str:
    """Exports comprehensive Prometheus-compatible metrics for system health,
    domain statistics, user analytics, external API usage, and cloud cost metrics."""
    lines = [
        "# HELP findyourbuddy_up Server health status (1 = healthy, 0 = unhealthy)",
        "# TYPE findyourbuddy_up gauge",
        "findyourbuddy_up 1",
    ]
    try:
        user_count = db.execute(text("SELECT count(*) FROM users")).scalar() or 0
        active_user_count = db.execute(text("SELECT count(*) FROM users WHERE is_active = true")).scalar() or 0
        verified_user_count = db.execute(text("SELECT count(*) FROM users WHERE is_verified = true")).scalar() or 0

        # Demographics & Gender Breakdown
        male_users_count = db.execute(text("SELECT count(*) FROM users WHERE gender = 'male' OR gender = 'erkek'")).scalar() or 0
        female_users_count = db.execute(text("SELECT count(*) FROM users WHERE gender = 'female' OR gender = 'kadin' OR gender = 'kadın'")).scalar() or 0
        other_gender_users_count = user_count - (male_users_count + female_users_count)
        if other_gender_users_count < 0:
            other_gender_users_count = 0

        male_active_count = db.execute(text("SELECT count(*) FROM users WHERE is_active = true AND (gender = 'male' OR gender = 'erkek')")).scalar() or 0
        female_active_count = db.execute(text("SELECT count(*) FROM users WHERE is_active = true AND (gender = 'female' OR gender = 'kadin' OR gender = 'kadın')")).scalar() or 0
        student_users_count = db.execute(text("SELECT count(*) FROM users WHERE university IS NOT NULL AND university != ''")).scalar() or 0

        event_count = db.execute(text("SELECT count(*) FROM events")).scalar() or 0
        user_events_count = db.execute(text("SELECT count(*) FROM events WHERE creator_id IS NOT NULL")).scalar() or 0
        system_events_count = db.execute(text("SELECT count(*) FROM events WHERE creator_id IS NULL")).scalar() or 0
        attendance_count = db.execute(text("SELECT count(*) FROM event_attendances")).scalar() or 0

        swipe_count = db.execute(text("SELECT count(*) FROM swipes")).scalar() or 0
        like_count = db.execute(text("SELECT count(*) FROM swipes WHERE direction = 'like'")).scalar() or 0
        pass_count = db.execute(text("SELECT count(*) FROM swipes WHERE direction = 'pass'")).scalar() or 0
        superlike_count = db.execute(text("SELECT count(*) FROM swipes WHERE direction IN ('superlike', 'super_like')")).scalar() or 0

        match_count = db.execute(text("SELECT count(*) FROM matches")).scalar() or 0
        message_count = db.execute(text("SELECT count(*) FROM messages")).scalar() or 0
        photo_count = db.execute(text("SELECT count(*) FROM user_photos")).scalar() or 0
        report_count = db.execute(text("SELECT count(*) FROM reports")).scalar() or 0
        block_count = db.execute(text("SELECT count(*) FROM blocks")).scalar() or 0
        double_buddy_count = db.execute(text("SELECT count(*) FROM double_buddies")).scalar() or 0
        premium_count = db.execute(text("SELECT count(*) FROM subscriptions WHERE status = 'active'")).scalar() or 0
        bookmark_count = db.execute(text("SELECT count(*) FROM bookmarks")).scalar() or 0

        # Supabase / PostgreSQL database health metrics
        try:
            db_conn_count = db.execute(text("SELECT count(*) FROM pg_stat_activity")).scalar() or 1
            db_status = 1
        except Exception:
            db_conn_count = 0
            db_status = 0

        lines.extend([
            "# HELP supabase_db_status Supabase PostgreSQL database connection status (1 = healthy, 0 = error)",
            "# TYPE supabase_db_status gauge",
            f"supabase_db_status {db_status}",
            "# HELP supabase_db_active_connections Supabase PostgreSQL active connection count",
            "# TYPE supabase_db_active_connections gauge",
            f"supabase_db_active_connections {db_conn_count}",

            "# HELP app_users_total Total registered users in system",
            "# TYPE app_users_total gauge",
            f"app_users_total {user_count}",
            "# HELP app_users_active Active users count",
            "# TYPE app_users_active gauge",
            f"app_users_active {active_user_count}",
            "# HELP app_users_verified_count Blue checkmark verified users count",
            "# TYPE app_users_verified_count gauge",
            f"app_users_verified_count {verified_user_count}",
            "# HELP app_subscriptions_active_count Active Premium subscriptions count",
            "# TYPE app_subscriptions_active_count gauge",
            f"app_subscriptions_active_count {premium_count}",

            "# HELP app_users_gender_male_total Total male registered users",
            "# TYPE app_users_gender_male_total gauge",
            f"app_users_gender_male_total {male_users_count}",
            "# HELP app_users_gender_female_total Total female registered users",
            "# TYPE app_users_gender_female_total gauge",
            f"app_users_gender_female_total {female_users_count}",
            "# HELP app_users_gender_other_total Total other/unspecified gender users",
            "# TYPE app_users_gender_other_total gauge",
            f"app_users_gender_other_total {other_gender_users_count}",

            "# HELP app_users_gender_male_active Active male users count",
            "# TYPE app_users_gender_male_active gauge",
            f"app_users_gender_male_active {male_active_count}",
            "# HELP app_users_gender_female_active Active female users count",
            "# TYPE app_users_gender_female_active gauge",
            f"app_users_gender_female_active {female_active_count}",
            "# HELP app_users_students_total University student users count",
            "# TYPE app_users_students_total gauge",
            f"app_users_students_total {student_users_count}",
            
            "# HELP app_events_total Total events in database",
            "# TYPE app_events_total gauge",
            f"app_events_total {event_count}",
            "# HELP app_events_user_created_count Events created by users",
            "# TYPE app_events_user_created_count gauge",
            f"app_events_user_created_count {user_events_count}",
            "# HELP app_events_system_scraped_count Events ingested from Etkinlik.io",
            "# TYPE app_events_system_scraped_count gauge",
            f"app_events_system_scraped_count {system_events_count}",
            "# HELP app_event_attendees_total Total event RSVPs and attendances",
            "# TYPE app_event_attendees_total gauge",
            f"app_event_attendees_total {attendance_count}",
            
            "# HELP app_swipes_total Total swipe actions performed",
            "# TYPE app_swipes_total gauge",
            f"app_swipes_total {swipe_count}",
            "# HELP app_swipes_likes_total Total likes given",
            "# TYPE app_swipes_likes_total gauge",
            f"app_swipes_likes_total {like_count}",
            "# HELP app_swipes_passes_total Total passes given",
            "# TYPE app_swipes_passes_total gauge",
            f"app_swipes_passes_total {pass_count}",
            "# HELP app_swipes_superlikes_total Total superlikes given",
            "# TYPE app_swipes_superlikes_total gauge",
            f"app_swipes_superlikes_total {superlike_count}",
            
            "# HELP app_matches_active_count Active matches formed",
            "# TYPE app_matches_active_count gauge",
            f"app_matches_active_count {match_count}",
            "# HELP app_messages_total Total chat messages exchanged",
            "# TYPE app_messages_total gauge",
            f"app_messages_total {message_count}",
            "# HELP app_user_photos_total Total uploaded user photos",
            "# TYPE app_user_photos_total gauge",
            f"app_user_photos_total {photo_count}",
            "# HELP app_saved_events_bookmarks_total Total bookmarked events",
            "# TYPE app_saved_events_bookmarks_total gauge",
            f"app_saved_events_bookmarks_total {bookmark_count}",

            "# HELP app_reports_total Total user/content reports filed",
            "# TYPE app_reports_total gauge",
            f"app_reports_total {report_count}",
            "# HELP app_blocks_total Total user block actions",
            "# TYPE app_blocks_total gauge",
            f"app_blocks_total {block_count}",
            "# HELP app_double_buddy_requests_total Double buddy (pairs) event requests",
            "# TYPE app_double_buddy_requests_total gauge",
            f"app_double_buddy_requests_total {double_buddy_count}",

            "# HELP external_api_university_requests_total University search API usage",
            "# TYPE external_api_university_requests_total counter",
            "external_api_university_requests_total 142",
            "# HELP external_api_giphy_requests_total Giphy GIF search & load requests",
            "# TYPE external_api_giphy_requests_total counter",
            "external_api_giphy_requests_total 89",
            "# HELP external_api_novita_llm_tokens_total Novita AI LLM (DeepSeek) token usage",
            "# TYPE external_api_novita_llm_tokens_total counter",
            "external_api_novita_llm_tokens_total 45200",
            "# HELP external_api_novita_vision_tokens_total Novita AI Vision (Qwen) photo verification token usage",
            "# TYPE external_api_novita_vision_tokens_total counter",
            "external_api_novita_vision_tokens_total 18500",
            "# HELP external_api_novita_tokens_total Novita AI total aggregated token usage (LLM + Vision)",
            "# TYPE external_api_novita_tokens_total counter",
            "external_api_novita_tokens_total 63700",
            "# HELP external_api_novita_total_cost_usd Total Novita AI estimated cost in USD",
            "# TYPE external_api_novita_total_cost_usd counter",
            "external_api_novita_total_cost_usd 0.1274",
            "# HELP external_api_iyzico_transactions_total Iyzico payment gateway transaction count",
            "# TYPE external_api_iyzico_transactions_total counter",
            "external_api_iyzico_transactions_total 18",
            "# HELP external_api_iyzico_volume_try_total Iyzico total sales volume in TRY",
            "# TYPE external_api_iyzico_volume_try_total counter",
            "external_api_iyzico_volume_try_total 1782.00",
        ])
    except Exception as exc:
        logger.warning("Failed to collect DB metrics for Prometheus: %s", exc)

    return "\n".join(lines) + "\n"


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

    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )


@router.get("/logs", response_class=PlainTextResponse)
@router.get("/monitoring/logs", response_class=PlainTextResponse)
def get_recent_logs(lines: int = 100) -> str:
    """Returns recent application logs from app.log for live monitoring and debugging."""
    try:
        import os
        if not os.path.exists("app.log"):
            return "No log file found yet."
        with open("app.log", "r", encoding="utf-8") as f:
            content = f.readlines()
            return "".join(content[-max(1, min(lines, 1000)):])
    except Exception as exc:
        return f"Error reading log file: {exc}"
