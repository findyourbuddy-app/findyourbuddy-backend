from sqlalchemy.orm import Session

from app.models.user import User


class UserNotFoundError(Exception):
    pass


def list_users(db: Session, skip: int = 0, limit: int = 50) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()


def set_user_active_status(db: Session, user_id: int, is_active: bool) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError(user_id)

    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user
