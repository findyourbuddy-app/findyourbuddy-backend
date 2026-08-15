from datetime import datetime, timedelta
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Form, responses
from sqlalchemy.orm import Session
import iyzipay

from app.config import get_settings
from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.subscription import SubscriptionStatus
from app.services.subscription_service import get_subscription, grant_premium, is_premium

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


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
    current_user: User = Depends(get_current_user),
) -> dict:
    """Creates a hosted Iyzico checkout form session for subscribing to premium."""
    settings = get_settings()
    options = {
        'api_key': settings.iyzico_api_key,
        'secret_key': settings.iyzico_secret_key,
        'base_url': settings.iyzico_base_url
    }

    # Format request payload for Iyzico Checkout Form
    request_data = {
        'locale': 'tr',
        'conversationId': f'sub_{current_user.id}_{int(datetime.utcnow().timestamp())}',
        'price': '99.00',
        'paidPrice': '99.00',
        'currency': 'TRY',
        'basketId': f'basket_{current_user.id}',
        'paymentGroup': 'SUBSCRIPTION',
        'callbackUrl': settings.public_base_url + "/subscriptions/callback",
        
        'buyer': {
            'id': str(current_user.id),
            'name': current_user.display_name or 'Buddy',
            'surname': 'User',
            'gsmNumber': '+905300000000',
            'email': current_user.email,
            'identityNumber': '11111111111',
            'lastLoginDate': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'registrationDate': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'registrationAddress': 'Kadikoy, Istanbul',
            'ip': '85.100.100.100',
            'city': 'Istanbul',
            'country': 'Turkey',
            'zipCode': '34700'
        },
        'shippingAddress': {
            'contactName': current_user.display_name or 'Buddy User',
            'city': 'Istanbul',
            'country': 'Turkey',
            'address': 'Kadikoy, Istanbul',
            'zipCode': '34700'
        },
        'billingAddress': {
            'contactName': current_user.display_name or 'Buddy User',
            'city': 'Istanbul',
            'country': 'Turkey',
            'address': 'Kadikoy, Istanbul',
            'zipCode': '34700'
        },
        'basketItems': [
            {
                'id': 'premium_monthly',
                'name': 'FindYourBuddy Premium 1 Month',
                'category1': 'Subscriptions',
                'itemType': 'VIRTUAL',
                'price': '99.00'
            }
        ]
    }

    try:
        # iyzipay's create()/retrieve() return a raw, unread http.client.HTTPResponse --
        # it must be read and JSON-decoded before any of the payload fields exist.
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
        'base_url': settings.iyzico_base_url
    }
    
    try:
        raw_response = iyzipay.CheckoutForm().retrieve({'token': token}, options)
        checkout_form = json.loads(raw_response.read().decode("utf-8"))
        status = checkout_form.get("status")
        payment_status = checkout_form.get("paymentStatus")

        if status == "success" and payment_status == "SUCCESS":
            conv_id = checkout_form.get("conversationId")
            if conv_id and conv_id.startswith("sub_"):
                parts = conv_id.split("_")
                user_id = int(parts[1])
                expires = datetime.utcnow() + timedelta(days=30)
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
    except Exception as e:
        logger.error(f"Iyzico callback verification error: {e}")
        return responses.HTMLResponse(content=f"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 100px; background: #121212; color: #fff;">
                    <h1 style="color: #F44336;">❌ Bir Hata Oluştu</h1>
                    <p>{str(e)}</p>
                </body>
            </html>
        """)
