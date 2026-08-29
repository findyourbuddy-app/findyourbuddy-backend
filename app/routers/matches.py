from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.datetime_utils import utcnow
from app.core.deps import get_current_user
from app.database import get_db
from app.models.event import Event
from app.models.match import Match
from app.models.match_feedback import MatchFeedback
from app.models.user import User
from app.schemas.match import MatchRead
from app.schemas.match_feedback import MatchFeedbackCreate
from app.schemas.message import MessageRead
from app.schemas.user import UserPublic
from app.services.match_feedback_service import (
    EventNotFinishedError,
    MatchNotFoundError,
    NotAMatchParticipantError,
    submit_feedback,
)
from app.services.matching_service import (
    UnmatchForbiddenError,
    UnmatchNotFoundError,
    list_matches_with_details,
    unmatch,
)

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/", response_model=list[MatchRead])
def list_my_matches(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MatchRead]:
    matches_details = list_matches_with_details(db, current_user.id, skip=skip, limit=limit)
    if not matches_details:
        return []

    # Batch query finished event IDs and submitted feedback match IDs in 2 queries total
    event_ids = {m.event_id for m, _, _ in matches_details if m.event_id}
    finished_event_ids: set[int] = set()
    if event_ids:
        now = utcnow()
        finished_event_ids = {
            r[0]
            for r in db.query(Event.id)
            .filter(Event.id.in_(event_ids), Event.starts_at < now)
            .all()
        }

    match_ids = [m.id for m, _, _ in matches_details]
    submitted_feedback_match_ids: set[int] = set()
    if match_ids:
        submitted_feedback_match_ids = {
            r[0]
            for r in db.query(MatchFeedback.match_id)
            .filter(
                MatchFeedback.match_id.in_(match_ids),
                MatchFeedback.rater_id == current_user.id,
            )
            .all()
        }

    return [
        MatchRead(
            id=match.id,
            event_id=match.event_id,
            event_title=match.event.title if match.event else None,
            event_category=match.event.category if match.event else None,
            event_is_group=match.event.is_group_event if match.event else False,
            event_creator_id=match.event.creator_id if match.event else None,
            user_a_id=match.user_a_id,
            user_b_id=match.user_b_id,
            score=match.score,
            created_at=match.created_at,
            other_user=UserPublic.model_validate(other_user),
            last_message=MessageRead.model_validate(last_message) if last_message else None,
            needs_feedback=(
                match.event_id in finished_event_ids
                and match.id not in submitted_feedback_match_ids
            ),
        )
        for match, other_user, last_message in matches_details
    ]


@router.post("/{match_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def submit_match_feedback(
    match_id: int,
    data: MatchFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        submit_feedback(db, match_id, current_user.id, data.met_in_person)
    except MatchNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found") from exc
    except NotAMatchParticipantError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant") from exc
    except EventNotFinishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Event has not finished yet"
        ) from exc


@router.delete("/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_match(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        unmatch(db, match_id, current_user.id)
    except UnmatchNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found") from exc
    except UnmatchForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant in this match") from exc


@router.get("/by-event/{event_id}", response_model=MatchRead)
def get_match_by_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MatchRead:
    match = (
        db.query(Match)
        .filter(
            Match.event_id == event_id,
            Match.is_active.is_(True),
            or_(Match.user_a_id == current_user.id, Match.user_b_id == current_user.id),
        )
        .first()
    )
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No match found for this event")

    other_user_id = match.user_b_id if match.user_a_id == current_user.id else match.user_a_id
    other_user = db.get(User, other_user_id)
    if not other_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match user not found")

    from app.models.message import Message
    last_message = (
        db.query(Message)
        .filter(Message.match_id == match.id)
        .order_by(Message.created_at.desc())
        .first()
    )

    return MatchRead(
        id=match.id,
        event_id=match.event_id,
        event_title=match.event.title if match.event else None,
        event_category=match.event.category if match.event else None,
        event_is_group=match.event.is_group_event if match.event else False,
        event_creator_id=match.event.creator_id if match.event else None,
        user_a_id=match.user_a_id,
        user_b_id=match.user_b_id,
        score=match.score,
        created_at=match.created_at,
        other_user=UserPublic.model_validate(other_user),
        last_message=MessageRead.model_validate(last_message) if last_message else None,
        needs_feedback=False,
    )
