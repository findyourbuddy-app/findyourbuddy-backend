from datetime import datetime, timedelta, timezone
from html import escape
from app.core.datetime_utils import utcnow
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Form, Request, responses
from sqlalchemy.orm import Session
import iyzipay

from app.config import get_settings
from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.subscription import SubscriptionStatus
from app.services.payment_service import claim_payment_callback
from app.services.subscription_service import get_subscription, grant_premium, is_premium

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

_PRICE_TOLERANCE = 0.01


@router.get("/me", response_model=SubscriptionStatus)
def read_my_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionStatus:
    subscription = get_subscription(db, current_user.id)
    return SubscriptionStatus(
        is_premium=is_premium(db, current_user.id),
        expires_at=subscription.expires_at if subscription else None,
    )


@router.post("/checkout-session")
def create_checkout_session(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Creates a hosted Iyzico checkout form session for subscribing to premium."""
    settings = get_settings()
    options = {
        'api_key': settings.iyzico_api_key,
        'secret_key': settings.iyzico_secret_key,
        'base_url': settings.iyzico_base_url,
    }

    now = utcnow()
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "0.0.0.0").split(",")[0].strip()
    gsm = current_user.phone_number or "+905300000000"
    price = settings.subscription_price_try

    request_data = {
        'locale': 'tr',
        'conversationId': f'sub_{current_user.id}_{int(now.timestamp())}',
        'price': price,
        'paidPrice': price,
        'currency': 'TRY',
        'basketId': f'basket_{current_user.id}',
        'paymentGroup': 'SUBSCRIPTION',
        'callbackUrl': settings.public_base_url + "/subscriptions/callback",
        'buyer': {
            'id': str(current_user.id),
            'name': current_user.display_name or 'Buddy',
            'surname': 'User',
            'gsmNumber': gsm,
            'email': current_user.email,
            'identityNumber': settings.iyzico_buyer_identity_number,
            'lastLoginDate': now.strftime('%Y-%m-%d %H:%M:%S'),
            'registrationDate': now.strftime('%Y-%m-%d %H:%M:%S'),
            'registrationAddress': 'Turkey',
            'ip': client_ip,
            'city': 'Istanbul',
            'country': 'Turkey',
            'zipCode': '34700',
        },
        'shippingAddress': {
            'contactName': current_user.display_name or 'Buddy User',
            'city': 'Istanbul',
            'country': 'Turkey',
            'address': 'Turkey',
            'zipCode': '34700',
        },
        'billingAddress': {
            'contactName': current_user.display_name or 'Buddy User',
            'city': 'Istanbul',
            'country': 'Turkey',
            'address': 'Turkey',
            'zipCode': '34700',
        },
        'basketItems': [
            {
                'id': 'premium_monthly',
                'name': 'FindYourBuddy Premium 1 Month',
                'category1': 'Subscriptions',
                'itemType': 'VIRTUAL',
                'price': price,
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
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/callback")
async def iyzico_callback(
    token: str = Form(...),
    db: Session = Depends(get_db),
):
    """Processes Iyzico payment redirection callback to verify and activate premium."""
    settings = get_settings()
    options = {
        'api_key': settings.iyzico_api_key,
        'secret_key': settings.iyzico_secret_key,
        'base_url': settings.iyzico_base_url,
    }
    expected_price = settings.subscription_price_try

    try:
        raw_response = iyzipay.CheckoutForm().retrieve({'token': token}, options)
        checkout_form = json.loads(raw_response.read().decode("utf-8"))
        checkout_status = checkout_form.get("status")
        payment_status = checkout_form.get("paymentStatus")

        if checkout_status == "success" and payment_status == "SUCCESS":
            paid_price_raw = str(checkout_form.get("paidPrice") or checkout_form.get("price") or "0")
            try:
                paid = float(paid_price_raw)
            except ValueError:
                paid = 0.0
            if paid < float(expected_price) - _PRICE_TOLERANCE:
                logger.warning("Price mismatch in subscription callback: expected %s, got %s", expected_price, paid_price_raw)
                return responses.HTMLResponse(
                    content="<html><body><h1>Ödeme Tutarı Geçersiz</h1></body></html>",
                    status_code=400,
                )

            conv_id = checkout_form.get("conversationId")
            if conv_id and conv_id.startswith("sub_"):
                parts = conv_id.split("_")
                try:
                    user_id = int(parts[1])
                except (IndexError, ValueError):
                    logger.error("Invalid conversationId format in callback: %s", conv_id)
                    return responses.HTMLResponse(
                        content="<html><body><h1>Geçersiz İşlem</h1></body></html>",
                        status_code=400,
                    )
                if claim_payment_callback(db, token, "subscription", user_id):
                    expires = utcnow() + timedelta(days=30)
                    grant_premium(db, user_id, expires_at=expires)

                return responses.HTMLResponse(content="""
                    <html>
                        <head>
                            <meta charset="utf-8">
                            <title>Ödeme Başarılı</title>
                        </head>
                        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; text-align: center; padding-top: 100px; background: #121214; color: #ffffff;">
                            <div style="max-width: 400px; margin: 0 auto; background: #1a1a1e; padding: 40px; border-radius: 16px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);">
                                <div style="font-size: 64px; margin-bottom: 20px;">🎉</div>
                                <h1 style="color: #4CAF50; font-size: 24px; margin-bottom: 10px;">Premium Aktif Edildi!</h1>
                                <p style="color: #c9c9cf; font-size: 14px; line-height: 1.5; margin-bottom: 30px;">FindYourBuddy Premium dünyasına hoş geldiniz. Ayrıcalıklarınızı hemen kullanmaya başlayabilirsiniz.</p>
                                <p style="color: #8c8c96; font-size: 12px;">Bu ekran 5 saniye içinde kapanacaktır.</p>
                            </div>
                            <script>setTimeout(function() { window.close(); }, 5000);</script>
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
    except Exception as e:
        logger.error("Iyzico callback verification error: %s", e)
        return responses.HTMLResponse(content="""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 100px; background: #121212; color: #fff;">
                    <h1 style="color: #F44336;">❌ Bir Hata Oluştu</h1>
                    <p>Lütfen daha sonra tekrar deneyin.</p>
                </body>
            </html>
        """)
