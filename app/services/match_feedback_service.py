from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.notifications import NotificationSender
from app.models.event import Event
from app.models.match import Match
from app.models.match_feedback import MatchFeedback
from app.models.notification import Notification
from app.models.user import User


class MatchNotFoundError(Exception):
    pass


class NotAMatchParticipantError(Exception):
    pass


class EventNotFinishedError(Exception):
    pass


def _other_user_id(match: Match, user_id: int) -> int:
    return match.user_b_id if match.user_a_id == user_id else match.user_a_id


def _get_feedback(db: Session, match_id: int, rater_id: int) -> MatchFeedback | None:
    return (
        db.query(MatchFeedback)
        .filter(MatchFeedback.match_id == match_id, MatchFeedback.rater_id == rater_id)
        .first()
    )


def event_has_finished(db: Session, event_id: int) -> bool:
    event = db.get(Event, event_id)
    return event is not None and event.starts_at < datetime.now(timezone.utc)


def needs_feedback(db: Session, match: Match, user_id: int) -> bool:
    """Drives the lightweight, dismissible in-chat prompt. True only for the
    window before anything has happened yet (no answer, no dismiss, no
    system notification) -- once any of those occur, the prompt has done its
    job (the user answered, skipped, or was already reached via a
    notification) and the in-app banner should not resurface."""
    if not event_has_finished(db, match.event_id):
        return False
    return _get_feedback(db, match.id, user_id) is None


def submit_feedback(
    db: Session, match_id: int, rater_id: int, met_in_person: bool | None
) -> MatchFeedback:
    match = db.get(Match, match_id)
    if match is None:
        raise MatchNotFoundError(match_id)
    if rater_id not in (match.user_a_id, match.user_b_id):
        raise NotAMatchParticipantError(rater_id)
    if not event_has_finished(db, match.event_id):
        raise EventNotFinishedError(match.event_id)

    feedback = _get_feedback(db, match_id, rater_id)
    if feedback is None:
        feedback = MatchFeedback(
            match_id=match_id, rater_id=rater_id, rated_id=_other_user_id(match, rater_id)
        )
        db.add(feedback)

    was_confirmed = feedback.met_in_person is True
    feedback.met_in_person = met_in_person
    db.commit()
    db.refresh(feedback)

    if met_in_person is True and not was_confirmed:
        rated_user = db.get(User, feedback.rated_id)
        if rated_user is not None:
            rated_user.trust_score += 1
            db.commit()

    return feedback


def send_pending_feedback_notifications(db: Session, sender: NotificationSender) -> int:
    """Nudges participants of finished-event matches who haven't been asked
    yet, via a plain notification (never a blocking screen). Idempotent:
    each participant is notified at most once per match."""
    finished_matches = (
        db.query(Match)
        .join(Event, Event.id == Match.event_id)
        .filter(Event.starts_at < datetime.now(timezone.utc))
        .all()
    )

    title = "Etkinlik nasıldı?"
    sent = 0
    for match in finished_matches:
        for user_id in (match.user_a_id, match.user_b_id):
            feedback = _get_feedback(db, match.id, user_id)
            if feedback is not None:
                continue
            body = "Kankanla buluştun mu? Sohbet ekranından hızlıca belirtebilirsin."
            db.add(
                MatchFeedback(
                    match_id=match.id,
                    rater_id=user_id,
                    rated_id=_other_user_id(match, user_id),
                    met_in_person=None,
                    notified_at=datetime.now(timezone.utc),
                )
            )
            sender.send(user_id, title, body)
            db.add(Notification(user_id=user_id, title=title, body=body))
            sent += 1
    db.commit()
    return sent
