import io
import json
import logging
from datetime import datetime

import iyzipay
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, responses, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
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
from app.services.payment_service import claim_payment_callback
from app.services.user_photo_service import (
    PhotoNotFoundError,
    TooManyPhotosError,
    add_photo,
    list_photos,
    remove_photo,
)
from app.services.user_service import delete_account, update_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])

PURCHASE_ITEM_NAMES = {
    "boost": "1 Adet Spotlight (Boost)",
    "super_likes": "5 Adet Süper Beğeni",
    "swipes": "50 Ekstra Kaydırma",
}
PURCHASE_ITEM_PRICES_TRY = {
    "boost": "39.00",
    "super_likes": "19.00",
    "swipes": "29.00",
}


def _apply_purchase(user: User, item_type: str, quantity: int) -> None:
    if item_type == "boost":
        user.boosts_balance += quantity
    elif item_type == "super_likes":
        user.extra_super_likes += quantity
    elif item_type == "swipes":
        user.bonus_swipe_credits += quantity * 50  # 50 extra swipes per package


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


class VerifyPhotoPayload(BaseModel):
    selfie_photo_url: str


@router.post("/me/verify-photo")
def verify_user_photo(
    payload: VerifyPhotoPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.vision_verification_service import verify_user_photo_with_vision
    return verify_user_photo_with_vision(db, current_user, payload.selfie_photo_url)


@router.get("/ai-match-llm/{target_user_id}")
def get_ai_match_llm(
    target_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.llm_matching_service import generate_llm_kanka_synergy
    target_user = db.get(User, target_user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return generate_llm_kanka_synergy(current_user, target_user)


ZODIAC_ELEMENTS = {
    "Koç": "Fire", "Aslan": "Fire", "Yay": "Fire",
    "Boğa": "Earth", "Başak": "Earth", "Oğlak": "Earth",
    "İkizler": "Air", "Terazi": "Air", "Kova": "Air",
    "Yengeç": "Water", "Akrep": "Water", "Balık": "Water"
}

ZODIAC_ELEMENT_SYNERGY = {
    ("Fire", "Fire"): 1.0, ("Fire", "Air"): 1.0, ("Fire", "Earth"): 0.5, ("Fire", "Water"): 0.3,
    ("Earth", "Earth"): 1.0, ("Earth", "Water"): 1.0, ("Earth", "Air"): 0.5, ("Earth", "Fire"): 0.5,
    ("Air", "Air"): 1.0, ("Air", "Fire"): 1.0, ("Air", "Water"): 0.5, ("Air", "Earth"): 0.5,
    ("Water", "Water"): 1.0, ("Water", "Earth"): 1.0, ("Water", "Fire"): 0.3, ("Water", "Air"): 0.5,
}

def calculate_ai_score(user_a: User, user_b: User) -> float:
    # 1. Ortak Hobiler & Aktiviteler (%45 Ağırlık)
    interests_a = user_a.interests or []
    interests_b = user_b.interests or []
    shared_interests = set(interests_a) & set(interests_b)
    total_interests = set(interests_a) | set(interests_b)
    interest_jaccard = len(shared_interests) / len(total_interests) if total_interests else 0.0

    hobbies_a = user_a.hobbies or []
    hobbies_b = user_b.hobbies or []
    shared_hobbies = set(hobbies_a) & set(hobbies_b)
    total_hobbies = set(hobbies_a) | set(hobbies_b)
    hobby_jaccard = len(shared_hobbies) / len(total_hobbies) if total_hobbies else 0.0

    if total_interests and total_hobbies:
        combined_interest_hobby = 0.5 * interest_jaccard + 0.5 * hobby_jaccard
    elif total_hobbies:
        combined_interest_hobby = hobby_jaccard
    else:
        combined_interest_hobby = interest_jaccard
    
    interests_hobbies_score = combined_interest_hobby * 45.0

    # 2. Astrolojik Element Sinerjisi (%25 Ağırlık)
    zodiac_score = 10.0
    if user_a.zodiac_sign and user_b.zodiac_sign:
        el_a = ZODIAC_ELEMENTS.get(user_a.zodiac_sign)
        el_b = ZODIAC_ELEMENTS.get(user_b.zodiac_sign)
        if el_a and el_b:
            synergy_ratio = ZODIAC_ELEMENT_SYNERGY.get((el_a, el_b), 0.5)
            zodiac_score = synergy_ratio * 25.0

    # 3. Mesafe ve Konum Analizi (%30 Ağırlık)
    location_score = 15.0
    has_coords = None not in (user_a.latitude, user_a.longitude, user_b.latitude, user_b.longitude)
    if has_coords:
        from app.core.geo import haversine_km
        dist = haversine_km(user_a.latitude, user_a.longitude, user_b.latitude, user_b.longitude)
        location_score = max(0.0, (1.0 - dist / 100.0) * 30.0)

    total_score = interests_hobbies_score + zodiac_score + location_score
    return round(min(99.0, max(50.0, total_score)), 1)


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


@router.post("/me/purchase/checkout-session")
def create_purchase_checkout_session(
    payload: PurchaseRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Creates a hosted Iyzico checkout form session for a Buddy Mağazası
    item, mirroring subscriptions.create_checkout_session -- purchases here
    used to just mutate balances with no real payment at all."""
    if payload.item_type not in PURCHASE_ITEM_PRICES_TRY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid item type")

    settings = get_settings()
    price = PURCHASE_ITEM_PRICES_TRY[payload.item_type]
    options = {
        "api_key": settings.iyzico_api_key,
        "secret_key": settings.iyzico_secret_key,
        "base_url": settings.iyzico_base_url,
    }
    request_data = {
        "locale": "tr",
        "conversationId": f"purchase_{payload.item_type}_{payload.quantity}_{current_user.id}_{int(datetime.utcnow().timestamp())}",
        "price": price,
        "paidPrice": price,
        "currency": "TRY",
        "basketId": f"basket_{current_user.id}",
        "paymentGroup": "PRODUCT",
        "callbackUrl": settings.public_base_url + "/users/me/purchase/callback",
        "buyer": {
            "id": str(current_user.id),
            "name": current_user.display_name or "Buddy",
            "surname": "User",
            "gsmNumber": "+905300000000",
            "email": current_user.email,
            "identityNumber": "11111111111",
            "lastLoginDate": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "registrationDate": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "registrationAddress": "Kadikoy, Istanbul",
            "ip": "85.100.100.100",
            "city": "Istanbul",
            "country": "Turkey",
            "zipCode": "34700",
        },
        "shippingAddress": {
            "contactName": current_user.display_name or "Buddy User",
            "city": "Istanbul",
            "country": "Turkey",
            "address": "Kadikoy, Istanbul",
            "zipCode": "34700",
        },
        "billingAddress": {
            "contactName": current_user.display_name or "Buddy User",
            "city": "Istanbul",
            "country": "Turkey",
            "address": "Kadikoy, Istanbul",
            "zipCode": "34700",
        },
        "basketItems": [
            {
                "id": payload.item_type,
                "name": PURCHASE_ITEM_NAMES[payload.item_type],
                "category1": "BuddyStore",
                "itemType": "VIRTUAL",
                "price": price,
            }
        ],
    }

    try:
        raw_response = iyzipay.CheckoutFormInitialize().create(request_data, options)
        response = json.loads(raw_response.read().decode("utf-8"))
        if response.get("status") == "success":
            return {"checkout_url": response.get("paymentPageUrl")}
        raise HTTPException(
            status_code=400, detail=response.get("errorMessage") or "Ödeme başlatılamadı."
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/me/purchase/callback")
async def purchase_callback(
    token: str = Form(...),
    db: Session = Depends(get_db),
):
    """Processes Iyzico payment redirection callback to verify and grant the
    purchased Buddy Mağazası item, mirroring subscriptions.iyzico_callback."""
    settings = get_settings()
    options = {
        "api_key": settings.iyzico_api_key,
        "secret_key": settings.iyzico_secret_key,
        "base_url": settings.iyzico_base_url,
    }

    try:
        raw_response = iyzipay.CheckoutForm().retrieve({"token": token}, options)
        checkout_form = json.loads(raw_response.read().decode("utf-8"))
        checkout_status = checkout_form.get("status")
        payment_status = checkout_form.get("paymentStatus")

        if checkout_status == "success" and payment_status == "SUCCESS":
            conv_id = checkout_form.get("conversationId")
            if conv_id and conv_id.startswith("purchase_"):
                # item_type itself can contain underscores (e.g. "super_likes"),
                # so split the fixed-shape numeric suffix off the right end
                # instead of assuming every "_"-separated part is one field.
                remainder = conv_id[len("purchase_"):]
                item_type, quantity, user_id, _timestamp = remainder.rsplit("_", 3)
                if claim_payment_callback(db, token, "purchase", int(user_id)):
                    user = db.get(User, int(user_id))
                    if user is not None:
                        _apply_purchase(user, item_type, int(quantity))
                        db.commit()
                return responses.HTMLResponse(content=f"""
                    <html>
                        <head>
                            <meta charset="utf-8">
                            <title>Ödeme Başarılı</title>
                        </head>
                        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; text-align: center; padding-top: 100px; background: #121214; color: #ffffff;">
                            <div style="max-width: 400px; margin: 0 auto; background: #1a1a1e; padding: 40px; border-radius: 16px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);">
                                <div style="font-size: 64px; margin-bottom: 20px;">🎉</div>
                                <h1 style="color: #4CAF50; font-size: 24px; margin-bottom: 10px;">Satın Alım Başarılı!</h1>
                                <p style="color: #c9c9cf; font-size: 14px; line-height: 1.5; margin-bottom: 30px;">Ödemen hesabına tanımlandı.</p>
                                <p style="color: #8c8c96; font-size: 12px;">Bu ekran 5 saniye içinde kapanacaktır.</p>
                            </div>
                            <script>setTimeout(function() {{ window.close(); }}, 5000);</script>
                        </body>
                    </html>
                """)

        error_msg = checkout_form.get("errorMessage") or "Ödeme tamamlanamadı."
        return responses.HTMLResponse(content=f"""
            <html>
                <head>
                    <meta charset="utf-8">
                    <title>Ödeme Başarısız</title>
                </head>
                <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; text-align: center; padding-top: 100px; background: #121214; color: #ffffff;">
                    <div style="max-width: 400px; margin: 0 auto; background: #1a1a1e; padding: 40px; border-radius: 16px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);">
                        <div style="font-size: 64px; margin-bottom: 20px;">❌</div>
                        <h1 style="color: #F44336; font-size: 24px; margin-bottom: 10px;">Ödeme Başarısız</h1>
                        <p style="color: #c9c9cf; font-size: 14px; line-height: 1.5; margin-bottom: 30px;">{error_msg}</p>
                        <p style="color: #8c8c96; font-size: 12px;">Lütfen tekrar deneyin. Bu ekran 5 saniye içinde kapanacaktır.</p>
                    </div>
                    <script>setTimeout(function() {{ window.close(); }}, 5000);</script>
                </body>
            </html>
        """)
    except Exception as exc:
        logger.error(f"Iyzico purchase callback verification error: {exc}")
        return responses.HTMLResponse(content=f"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 100px; background: #121212; color: #fff;">
                    <h1 style="color: #F44336;">❌ Bir Hata Oluştu</h1>
                    <p>{str(exc)}</p>
                </body>
            </html>
        """)

