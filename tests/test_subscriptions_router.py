from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "s3cret-pass", "display_name": email, "accepted_terms": True, "phone_number": f"5{abs(hash(email)) % 10**9:09d}"},
    )
    response = client.post("/auth/login", json={"email": email, "password": "s3cret-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_staff(db_session: Session, user_id: int) -> None:
    staff_user = db_session.get(User, user_id)
    staff_user.is_staff = True
    db_session.commit()


def test_read_my_subscription_defaults_to_not_premium(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/subscriptions/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["is_premium"] is False


def test_non_staff_cannot_grant_premium(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]

    response = client.post(f"/admin/users/{a_id}/premium", headers=a_headers, json={})

    assert response.status_code == 403


def test_staff_can_grant_and_revoke_premium(client: TestClient, db_session: Session) -> None:
    staff_headers = _register_and_login(client, "staff@example.com")
    target_headers = _register_and_login(client, "target@example.com")
    staff_id = client.get("/users/me", headers=staff_headers).json()["id"]
    target_id = client.get("/users/me", headers=target_headers).json()["id"]
    _make_staff(db_session, staff_id)

    grant_response = client.post(
        f"/admin/users/{target_id}/premium", headers=staff_headers, json={}
    )
    assert grant_response.status_code == 200
    assert grant_response.json()["is_premium"] is True

    status_response = client.get("/subscriptions/me", headers=target_headers)
    assert status_response.json()["is_premium"] is True

    revoke_response = client.delete(f"/admin/users/{target_id}/premium", headers=staff_headers)
    assert revoke_response.status_code == 200
    assert revoke_response.json()["is_premium"] is False

    status_response = client.get("/subscriptions/me", headers=target_headers)
    assert status_response.json()["is_premium"] is False


import iyzipay

def test_create_checkout_session_iyzico(client: TestClient, auth_headers: dict[str, str], monkeypatch) -> None:
    # iyzipay's create()/retrieve() return a raw http.client.HTTPResponse, not a
    # parsed dict -- the router reads and JSON-decodes it, so the mock must too.
    import json

    dummy_body = json.dumps(
        {
            "status": "success",
            "paymentPageUrl": "https://sandbox-api.iyzipay.com/checkout/pay",
        }
    ).encode("utf-8")

    class FakeHTTPResponse:
        @staticmethod
        def read():
            return dummy_body

    class MockCreate:
        @staticmethod
        def create(request_data, options):
            return FakeHTTPResponse()

    monkeypatch.setattr(
        iyzipay,
        "CheckoutFormInitialize",
        lambda: MockCreate()
    )

    response = client.post("/subscriptions/checkout-session", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["checkout_url"] == "https://sandbox-api.iyzipay.com/checkout/pay"


def test_iyzico_callback_completed(client: TestClient, db_session: Session, monkeypatch) -> None:
    user_headers = _register_and_login(client, "buyer@example.com")
    user_id = client.get("/users/me", headers=user_headers).json()["id"]

    # Mock iyzipay.CheckoutForm().retrieve
    import json

    dummy_body = json.dumps(
        {
            "status": "success",
            "paymentStatus": "SUCCESS",
            "paidPrice": "99.00",
            "conversationId": f"sub_{user_id}_12345678",
        }
    ).encode("utf-8")

    class FakeHTTPResponse:
        @staticmethod
        def read():
            return dummy_body

    class MockRetrieve:
        @staticmethod
        def retrieve(request_data, options):
            return FakeHTTPResponse()

    monkeypatch.setattr(
        iyzipay,
        "CheckoutForm",
        lambda: MockRetrieve()
    )

    # Call callback endpoint via POST Form Data
    response = client.post(
        "/subscriptions/callback",
        data={"token": "dummy-iyzico-token"}
    )
    assert response.status_code == 200
    assert "Premium Aktif Edildi!" in response.text

    # Verify user was granted premium
    status_response = client.get("/subscriptions/me", headers=user_headers)
    assert status_response.json()["is_premium"] is True
    first_expires_at = status_response.json()["expires_at"]

    # A retried/duplicated callback for the same token must not extend the
    # subscription a second time.
    repeat_response = client.post(
        "/subscriptions/callback",
        data={"token": "dummy-iyzico-token"},
    )
    assert repeat_response.status_code == 200

    status_response = client.get("/subscriptions/me", headers=user_headers)
    assert status_response.json()["expires_at"] == first_expires_at

