from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.scheduler import run_cleanup_jobs
from app.schemas.event import EventCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user, request_password_reset, reset_password
from app.services.event_service import create_event


def test_run_cleanup_jobs_reports_deleted_counts(db_session: Session) -> None:
    user = register_user(
        db_session,
        UserCreate(
            email="ada@example.com", password="s3cret-pass", display_name="Ada", accepted_terms=True
        ),
    )
    create_event(
        db_session,
        EventCreate(
            title="Old",
            category="sports",
            location_name="Central Park",
            latitude=40.0,
            longitude=-73.0,
            starts_at=datetime.utcnow() - timedelta(days=100),
        ),
        user.id,
    )
    token = request_password_reset(db_session, "ada@example.com")
    assert token is not None
    reset_password(db_session, token, "new-secret-pass")

    result = run_cleanup_jobs(db_session)

    assert result == {"deleted_events": 1, "deleted_tokens": 1}
