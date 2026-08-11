from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.match import Match
from app.models.user import User
from app.schemas.match import MatchRead
from app.services.matching_service import list_matches_for_user

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/", response_model=list[MatchRead])
def list_my_matches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Match]:
    return list_matches_for_user(db, current_user.id)
