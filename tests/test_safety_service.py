import pytest
from sqlalchemy.orm import Session

from app.models.report import ReportReason
from app.schemas.safety import ReportCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.safety_service import (
    AlreadyBlockedError,
    CannotBlockSelfError,
    CannotReportSelfError,
    block_user,
    blocked_user_ids,
    create_report,
    is_blocked,
)


def _register(db_session: Session, email: str) -> int:
    return register_user(
        db_session, UserCreate(email=email, password="s3cret-pass", display_name=email)
    ).id


def test_block_user_creates_block(db_session: Session) -> None:
    blocker = _register(db_session, "blocker@example.com")
    blocked = _register(db_session, "blocked@example.com")

    block = block_user(db_session, blocker, blocked)

    assert block.blocker_id == blocker
    assert block.blocked_id == blocked


def test_cannot_block_self(db_session: Session) -> None:
    user = _register(db_session, "user@example.com")

    with pytest.raises(CannotBlockSelfError):
        block_user(db_session, user, user)


def test_cannot_block_same_user_twice(db_session: Session) -> None:
    blocker = _register(db_session, "blocker@example.com")
    blocked = _register(db_session, "blocked@example.com")
    block_user(db_session, blocker, blocked)

    with pytest.raises(AlreadyBlockedError):
        block_user(db_session, blocker, blocked)


def test_is_blocked_detects_either_direction(db_session: Session) -> None:
    a = _register(db_session, "a@example.com")
    b = _register(db_session, "b@example.com")
    block_user(db_session, a, b)

    assert is_blocked(db_session, a, b) is True
    assert is_blocked(db_session, b, a) is True


def test_blocked_user_ids_includes_both_directions(db_session: Session) -> None:
    a = _register(db_session, "a@example.com")
    b = _register(db_session, "b@example.com")
    c = _register(db_session, "c@example.com")
    block_user(db_session, a, b)
    block_user(db_session, c, a)

    assert set(blocked_user_ids(db_session, a)) == {b, c}


def test_create_report(db_session: Session) -> None:
    reporter = _register(db_session, "reporter@example.com")
    reported = _register(db_session, "reported@example.com")

    report = create_report(
        db_session,
        reporter,
        ReportCreate(reported_user_id=reported, reason=ReportReason.HARASSMENT, description="rude"),
    )

    assert report.reporter_id == reporter
    assert report.reported_user_id == reported
    assert report.status.value == "pending"


def test_cannot_report_self(db_session: Session) -> None:
    user = _register(db_session, "user@example.com")

    with pytest.raises(CannotReportSelfError):
        create_report(
            db_session, user, ReportCreate(reported_user_id=user, reason=ReportReason.OTHER)
        )
