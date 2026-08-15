from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.match import MatchRead
from app.schemas.match_feedback import MatchFeedbackCreate
from app.schemas.message import MessageRead
from app.schemas.user import UserPublic
from app.services.match_feedback_service import (
    EventNotFinishedError,
    MatchNotFoundError,
    NotAMatchParticipantError,
    needs_feedback,
    submit_feedback,
)
from app.services.matching_service import list_matches_with_details

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/", response_model=list[MatchRead])
def list_my_matches(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MatchRead]:
    return [
        MatchRead(
            id=match.id,
            event_id=match.event_id,
            user_a_id=match.user_a_id,
            user_b_id=match.user_b_id,
            score=match.score,
            created_at=match.created_at,
            other_user=UserPublic.model_validate(other_user),
            last_message=MessageRead.model_validate(last_message) if last_message else None,
            needs_feedback=needs_feedback(db, match, current_user.id),
        )
        for match, other_user, last_message in list_matches_with_details(
            db, current_user.id, skip=skip, limit=limit
        )
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
