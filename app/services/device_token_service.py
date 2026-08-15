from sqlalchemy.orm import Session

from app.models.device_token import DeviceToken


def register_device_token(db: Session, user_id: int, token: str) -> DeviceToken:
    existing = db.query(DeviceToken).filter(DeviceToken.token == token).first()
    if existing is not None:
        existing.user_id = user_id
        db.commit()
        db.refresh(existing)
        return existing

    device_token = DeviceToken(user_id=user_id, token=token)
    db.add(device_token)
    db.commit()
    db.refresh(device_token)
    return device_token


def unregister_device_token(db: Session, user_id: int, token: str) -> None:
    db.query(DeviceToken).filter(
        DeviceToken.user_id == user_id, DeviceToken.token == token
    ).delete()
    db.commit()
