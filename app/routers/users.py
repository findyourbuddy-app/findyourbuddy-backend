import io
import json
import logging
from html import escape
from datetime import datetime, timedelta, timezone
from app.core.datetime_utils import utcnow

import iyzipay
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, responses, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import get_current_user
from app.core.rate_limit import ai_rate_limit, limiter, messages_rate_limit
from app.database import get_db
from app.models.swipe import Swipe
from app.models.user import User
from app.models.user_photo import UserPhoto
from app.schemas.device_token import DeviceTokenCreate, DeviceTokenRead
from app.schemas.export import UserDataExport
from app.schemas.user import UserRead, UserUpdate, AIRecommendation
from app.schemas.user_photo import UserPhotoRead
from app.services.device_token_service import register_device_token, unregister_device_token
from app.services.export_service import export_user_data
from app.services.llm_matching_service import generate_llm_kanka_synergy
from app.services.media_service import MediaStorage, get_media_storage
from app.services.media_validation import (
    ImageTooLargeError,
    InvalidImageError,
    compress_image,
    validate_chat_image,
    validate_image,
)
from app.services.payment_service import apply_purchase, claim_payment_callback
from app.services.recommendation_service import RecommendationService
from app.services.safety_service import blocked_user_ids
from app.services.subscription_service import is_premium
from app.services.user_photo_service import (
    PhotoNotFoundError,
    TooManyPhotosError,
    add_photo,
    list_photos,
    remove_photo,
)
from app.services.user_service import delete_account, update_profile
from app.services.vision_verification_service import verify_user_photo_with_vision

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])

_PRICE_TOLERANCE = 0.01

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


def _upload_validated_photo(file: UploadFile, storage: MediaStorage) -> str:
    try:
        file.file.seek(0)
        data = validate_image(file.file)
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image file"
        ) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large"
        ) from exc

    compressed = compress_image(data)
    return storage.upload(io.BytesIO(compressed), "photo.jpg")


def _upload_chat_image(file: UploadFile, storage: MediaStorage) -> str:
    """Chat photos are stored at their original resolution -- unlike profile
    photos they are not downscaled or re-encoded."""
    try:
        file.file.seek(0)
        data, ext = validate_chat_image(file.file)
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image file"
        ) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large"
        ) from exc

    return storage.upload(io.BytesIO(data), f"chat{ext}")


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
@limiter.limit(messages_rate_limit)
def upload_chat_media(
    request: Request,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    storage: MediaStorage = Depends(get_media_storage),
) -> dict:
    url = _upload_chat_image(file, storage)
    return {"url": url}


_ALLOWED_VOICE_MIMES = {
    "audio/m4a",
    "audio/x-m4a",
    "audio/mp4",
    "audio/aac",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/3gpp",
    "audio/amr",
    "audio/caf",
    "application/octet-stream",
}
_ALLOWED_VOICE_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".caf", ".ogg", ".webm", ".3gp", ".mp4"}
_MAX_VOICE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/me/voice-note", response_model=UserRead)
def upload_voice_note(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> User:
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    filename = (file.filename or "voice_note.m4a").lower()
    ext = "." + filename.split(".")[-1] if "." in filename else ".m4a"

    if content_type not in _ALLOWED_VOICE_MIMES and ext not in _ALLOWED_VOICE_EXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported audio format",
        )
    data = file.file.read(_MAX_VOICE_BYTES + 1)
    if len(data) > _MAX_VOICE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Voice note too large (max 10 MB)",
        )
    url = storage.upload(io.BytesIO(data), file.filename or "voice_note.m4a")
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
@limiter.limit(ai_rate_limit)
def verify_user_photo(
    request: Request,
    payload: VerifyPhotoPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return verify_user_photo_with_vision(db, current_user, payload.selfie_photo_url)


@router.get("/ai-match-llm/{target_user_id}")
@limiter.limit(ai_rate_limit)
def get_ai_match_llm(
    request: Request,
    target_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_user = db.get(User, target_user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return generate_llm_kanka_synergy(current_user, target_user)


_AI_RECOMMENDATION_CANDIDATE_POOL = 30


@router.get("/me/ai-recommendations", response_model=list[AIRecommendation])
def get_ai_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AIRecommendation]:
    swiped_ids = {
        s.target_id
        for s in db.query(Swipe.target_id).filter(Swipe.swiper_id == current_user.id).all()
    }
    blocked_ids = set(blocked_user_ids(db, current_user.id))
    exclude_ids = swiped_ids | blocked_ids | {current_user.id}

    query = db.query(User).filter(User.is_active.is_(True))
    if exclude_ids:
        query = query.filter(User.id.not_in(exclude_ids))
    candidates = query.limit(_AI_RECOMMENDATION_CANDIDATE_POOL).all()

    results = sorted(
        [
            AIRecommendation(
                user=UserRead.model_validate(cand),
                match_score=RecommendationService.score_ai_recommendation(current_user, cand),
            )
            for cand in candidates
        ],
        key=lambda r: r.match_score,
        reverse=True,
    )
    return results[:10]


class PurchaseRequest(BaseModel):
    item_type: str  # "boost", "super_likes", "swipes"
    quantity: int = Field(default=1, ge=1, le=20)


@router.post("/me/boost", response_model=UserRead)
def activate_boost(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
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
    
    current_user.boosted_until = utcnow() + timedelta(minutes=60)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/purchase/checkout-session")
def create_purchase_checkout_session(
    request: Request,
    payload: PurchaseRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Creates a hosted Iyzico checkout form session for a Buddy Mağazası
    item, mirroring subscriptions.create_checkout_session -- purchases here
    used to just mutate balances with no real payment at all."""
    if payload.item_type not in PURCHASE_ITEM_PRICES_TRY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid item type")

    settings = get_settings()
    # PURCHASE_ITEM_PRICES_TRY values are strings ("39.00") for Iyzico's
    # request format -- multiply as a number, then reformat, or this becomes
    # string repetition ("39.00" * 3 == "39.0039.0039.00"). quantity is
    # capped (1-20) by the schema, so this can't overflow into an absurd total.
    unit_price = float(PURCHASE_ITEM_PRICES_TRY[payload.item_type])
    price = f"{unit_price * payload.quantity:.2f}"
    options = {
        "api_key": settings.iyzico_api_key,
        "secret_key": settings.iyzico_secret_key,
        "base_url": settings.iyzico_base_url,
    }
    now = utcnow()
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "0.0.0.0").split(",")[0].strip()
    gsm = current_user.phone_number or "+905300000000"

    request_data = {
        "locale": "tr",
        "conversationId": f"purchase_{payload.item_type}_{payload.quantity}_{current_user.id}_{int(now.timestamp())}",
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
            "gsmNumber": gsm,
            "email": current_user.email,
            "identityNumber": settings.iyzico_buyer_identity_number,
            "lastLoginDate": now.strftime("%Y-%m-%d %H:%M:%S"),
            "registrationDate": now.strftime("%Y-%m-%d %H:%M:%S"),
            "registrationAddress": "Turkey",
            "ip": client_ip,
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
                remainder = conv_id[len("purchase_"):]
                try:
                    item_type, quantity_str, user_id_str, _timestamp = remainder.rsplit("_", 3)
                    quantity = int(quantity_str)
                    user_id = int(user_id_str)
                except (ValueError, AttributeError):
                    logger.error("Invalid conversationId format in purchase callback: %s", conv_id)
                    return responses.HTMLResponse(
                        content="<html><body><h1>Geçersiz İşlem</h1></body></html>",
                        status_code=400,
                    )

                unit_price = PURCHASE_ITEM_PRICES_TRY.get(item_type)
                expected_price = float(unit_price) * quantity if unit_price else None
                paid_price = str(checkout_form.get("paidPrice") or checkout_form.get("price") or "")
                if expected_price and paid_price and float(paid_price) < expected_price - _PRICE_TOLERANCE:
                    logger.warning("Price mismatch in store purchase callback: expected %s, got %s", expected_price, paid_price)
                    return responses.HTMLResponse(content="<html><body><h1>Ödeme Tutarı Geçersiz</h1></body></html>", status_code=400)

                if claim_payment_callback(db, token, "purchase", user_id):
                    user = db.get(User, user_id)
                    if user is not None:
                        apply_purchase(user, item_type, quantity)
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

        error_msg = escape(checkout_form.get("errorMessage") or "Ödeme tamamlanamadı.")
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
                    <p>{escape(str(exc))}</p>
                </body>
            </html>
        """)


@router.get("/{user_id}", response_model=UserRead)
def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

