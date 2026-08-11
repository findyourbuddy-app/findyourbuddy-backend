from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.match import MatchRead
from app.schemas.message import MessageRead
from app.schemas.user import UserPublic
from app.services.matching_service import list_matches_with_details

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/", response_model=list[MatchRead])
def list_my_matches(
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
        )
        for match, other_user, last_message in list_matches_with_details(db, current_user.id)
    ]
