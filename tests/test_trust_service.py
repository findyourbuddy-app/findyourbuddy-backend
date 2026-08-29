from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.block import Block
from app.models.event import Event
from app.models.event_attendance import EventAttendance
from app.models.report import Report, ReportStatus
from app.models.user import User
from app.services.trust_service import compute_trust_score, recompute_trust_score

S = get_settings()


def _user(db: Session, email: str, **kw) -> User:
    user = User(
        email=email,
        hashed_password="hash",
        display_name=email,
        referral_code=email[:10].upper().ljust(6, "X"),
        phone_number=f"+9055{abs(hash(email)) % 10**8:08d}",
        **kw,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_fresh_unverified_user_sits_at_base(db_session: Session) -> None:
    user = _user(db_session, "fresh@example.com")
    assert compute_trust_score(db_session, user) == S.trust_base_score


def test_verification_flags_add_up(db_session: Session) -> None:
    user = _user(
        db_session,
        "verified@example.com",
        is_verified=True,
        phone_verified=True,
        firebase_uid="fb-123",
    )
    expected = (
        S.trust_base_score
        + S.trust_photo_verified_points
        + S.trust_phone_verified_points
        + S.trust_email_verified_points
    )
    assert compute_trust_score(db_session, user) == expected


def test_score_is_clamped_to_0_100(db_session: Session) -> None:
    user = _user(db_session, "reported@example.com")
    for i in range(6):
        reporter = _user(db_session, f"rep{i}@example.com")
        db_session.add(
            Report(
                reporter_id=reporter.id,
                reported_user_id=user.id,
                reason="spam",
                status=ReportStatus.REVIEWED,
            )
        )
    db_session.commit()
    assert compute_trust_score(db_session, user) == 0


def test_no_shows_and_blocks_pull_the_score_down(db_session: Session) -> None:
    user = _user(db_session, "flaky@example.com", is_verified=True)
    past = datetime.now(timezone.utc) - timedelta(days=2)
    event = Event(
        title="e", category="coffee", location_name="x", latitude=1.0, longitude=1.0, starts_at=past
    )
    db_session.add(event)
    db_session.commit()
    db_session.add(
        EventAttendance(
            event_id=event.id,
            user_id=user.id,
            status="approved",
            no_show_penalized_at=datetime.now(timezone.utc),
        )
    )
    blocker = _user(db_session, "blocker@example.com")
    db_session.add(Block(blocker_id=blocker.id, blocked_id=user.id))
    db_session.commit()

    score = compute_trust_score(db_session, user)
    verified_baseline = S.trust_base_score + S.trust_photo_verified_points
    assert score < verified_baseline


def test_recompute_persists(db_session: Session) -> None:
    user = _user(db_session, "persist@example.com", trust_score=99)
    new_score = recompute_trust_score(db_session, user.id)
    db_session.refresh(user)
    assert user.trust_score == new_score == S.trust_base_score
