import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.user_photo import UserPhoto
from app.schemas.device_token import DeviceTokenCreate, DeviceTokenRead
from app.schemas.export import UserDataExport
from app.schemas.user import UserRead, UserUpdate, AIRecommendation
from app.schemas.user_photo import UserPhotoRead
from app.services.device_token_service import register_device_token, unregister_device_token
from app.services.export_service import export_user_data
from app.services.media_service import MediaStorage, get_media_storage
from app.services.media_validation import ImageTooLargeError, InvalidImageError, validate_image
from app.services.user_photo_service import (
    PhotoNotFoundError,
    TooManyPhotosError,
    add_photo,
    list_photos,
    remove_photo,
)
from app.services.user_service import delete_account, update_profile

router = APIRouter(prefix="/users", tags=["users"])


def _upload_validated_photo(file: UploadFile, storage: MediaStorage) -> str:
    try:
        data = validate_image(file.file)
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image file"
        ) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large"
        ) from exc

    return storage.upload(io.BytesIO(data), file.filename or "photo")


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_current_user(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return update_profile(db, current_user, data)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    delete_account(db, current_user)


@router.get("/me/export", response_model=UserDataExport)
def export_current_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserDataExport:
    return export_user_data(db, current_user)


@router.post(
    "/me/device-tokens", response_model=DeviceTokenRead, status_code=status.HTTP_201_CREATED
)
def register_current_user_device_token(
    data: DeviceTokenCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceTokenRead:
    return register_device_token(db, current_user.id, data.token)


@router.delete("/me/device-tokens/{token}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_current_user_device_token(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    unregister_device_token(db, current_user.id, token)


@router.post("/me/photo", response_model=UserRead)
def upload_profile_photo(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> User:
    current_user.photo_url = _upload_validated_photo(file, storage)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/media", status_code=status.HTTP_201_CREATED)
def upload_chat_media(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    storage: MediaStorage = Depends(get_media_storage),
) -> dict:
    url = _upload_validated_photo(file, storage)
    return {"url": url}


@router.post("/me/voice-note", response_model=UserRead)
def upload_voice_note(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> User:
    url = storage.upload(file.file, file.filename or "voice_note.m4a")
    current_user.voice_note_url = url
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/photos", response_model=list[UserPhotoRead])
def list_my_photos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserPhoto]:
    return list_photos(db, current_user.id)


@router.post("/me/photos", response_model=UserPhotoRead, status_code=status.HTTP_201_CREATED)
def upload_my_photo(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> UserPhoto:
    photo_url = _upload_validated_photo(file, storage)
    try:
        return add_photo(db, current_user.id, photo_url)
    except TooManyPhotosError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Photo limit reached"
        ) from exc


@router.delete("/me/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_photo(
    photo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        remove_photo(db, current_user.id, photo_id)
    except PhotoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from exc


@router.post("/me/verify", response_model=UserRead)
def request_profile_verification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if current_user.verification_status in ("verified", "pending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Verification already {current_user.verification_status}"
        )
    current_user.verification_status = "pending"
    db.commit()
    db.refresh(current_user)
    return current_user


ZODIAC_ELEMENTS = {
    "Koç": "Fire", "Aslan": "Fire", "Yay": "Fire",
    "Boğa": "Earth", "Başak": "Earth", "Oğlak": "Earth",
    "İkizler": "Air", "Terazi": "Air", "Kova": "Air",
    "Yengeç": "Water", "Akrep": "Water", "Balık": "Water"
}

def calculate_ai_score(user_a: User, user_b: User) -> float:
    # 1. Interests (40%)
    interests_score = 0.0
    if user_a.interests and user_b.interests:
        shared = set(user_a.interests) & set(user_b.interests)
        total = set(user_a.interests) | set(user_b.interests)
        interests_score = (len(shared) / len(total)) * 40.0
        
    # 2. Zodiac (25%)
    zodiac_score = 5.0
    if user_a.zodiac_sign and user_b.zodiac_sign:
        el_a = ZODIAC_ELEMENTS.get(user_a.zodiac_sign)
        el_b = ZODIAC_ELEMENTS.get(user_b.zodiac_sign)
        if el_a and el_b and el_a == el_b:
            zodiac_score = 25.0
            
    # 3. Location (35%)
    location_score = 10.0
    has_coords = None not in (user_a.latitude, user_a.longitude, user_b.latitude, user_b.longitude)
    if has_coords:
        from app.core.geo import haversine_km
        dist = haversine_km(user_a.latitude, user_a.longitude, user_b.latitude, user_b.longitude)
        location_score = max(0.0, (1.0 - dist / 100.0) * 35.0)
        
    return interests_score + zodiac_score + location_score


@router.get("/me/ai-recommendations", response_model=list[AIRecommendation])
def get_ai_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AIRecommendation]:
    from app.models.swipe import Swipe
    from app.services.safety_service import blocked_user_ids
    
    # Get user IDs already swiped on by the user
    swiped_ids = {s.target_id for s in db.query(Swipe).filter(Swipe.swiper_id == current_user.id).all()}
    # Get user IDs blocked by the user
    blocked_ids = set(blocked_user_ids(db, current_user.id))
    
    exclude_ids = swiped_ids | blocked_ids | {current_user.id}
    
    query = db.query(User).filter(User.is_active.is_(True))
    if exclude_ids:
        query = query.filter(User.id.not_in(exclude_ids))
    candidates = query.all()
    
    results = []
    for cand in candidates:
        score = calculate_ai_score(current_user, cand)
        results.append(
            AIRecommendation(
                user=UserRead.model_validate(cand),
                match_score=round(score, 1)
            )
        )
        
    # Sort by match score in descending order
    results.sort(key=lambda r: r.match_score, reverse=True)
    return results[:10]


class PurchaseRequest(BaseModel):
    item_type: str  # "boost", "super_likes", "swipes"
    quantity: int = 1


@router.post("/me/boost", response_model=UserRead)
def activate_boost(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    from datetime import datetime, timedelta
    from app.services.subscription_service import is_premium
    
    premium = is_premium(db, current_user.id)
    
    # Check if they have boosts balance or premium free daily boost
    if not premium and current_user.boosts_balance <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please upgrade to Premium or buy a Boost to use Spotlight.",
        )
    
    # Use boost
    if current_user.boosts_balance > 0:
        current_user.boosts_balance -= 1
    
    current_user.boosted_until = datetime.utcnow() + timedelta(minutes=60)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/purchase", response_model=UserRead)
def purchase_items(
    payload: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if payload.item_type == "boost":
        current_user.boosts_balance += payload.quantity
    elif payload.item_type == "super_likes":
        current_user.extra_super_likes += payload.quantity
    elif payload.item_type == "swipes":
        current_user.bonus_swipe_credits += payload.quantity * 50  # 50 extra swipes per package
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid item type",
        )
    
    db.commit()
    db.refresh(current_user)
    return current_user

