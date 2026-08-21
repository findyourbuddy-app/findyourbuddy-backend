from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.config import get_settings
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.vision_verification_service import verify_user_photo_with_vision


def test_verify_user_photo_without_profile_photo(db_session) -> None:
    user = register_user(
        db_session,
        UserCreate(
            email="nophoto@example.com",
            password="Password123!",
            display_name="No Photo",
            accepted_terms=True,
            phone_number="5000000010"
        )
    )
    user.photo_url = None
    db_session.commit()

    result = verify_user_photo_with_vision(db_session, user, "http://example.com/selfie.jpg")
    assert result["verified"] is False
    assert "bulunamadı" in result["message"]


def test_verify_user_photo_without_api_key_in_production_fails(db_session, monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("NOVITA_API_KEY", "")
    monkeypatch.setenv("ENVIRONMENT", "production")

    user = register_user(
        db_session,
        UserCreate(
            email="prod_no_key@example.com",
            password="Password123!",
            display_name="Prod No Key",
            accepted_terms=True,
            phone_number="5000000011"
        )
    )
    user.photo_url = "http://example.com/main.jpg"
    db_session.commit()

    result = verify_user_photo_with_vision(db_session, user, "http://example.com/selfie.jpg")
    assert result["verified"] is False
    assert user.is_verified is False
    assert "kullanılamıyor" in result["message"]

    get_settings.cache_clear()


def test_verify_user_photo_without_api_key_in_development_auto_approves(db_session, monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("NOVITA_API_KEY", "")
    monkeypatch.setenv("ENVIRONMENT", "development")

    user = register_user(
        db_session,
        UserCreate(
            email="dev_no_key@example.com",
            password="Password123!",
            display_name="Dev No Key",
            accepted_terms=True,
            phone_number="5000000014"
        )
    )
    user.photo_url = "http://example.com/main.jpg"
    db_session.commit()

    result = verify_user_photo_with_vision(db_session, user, "http://example.com/selfie.jpg")
    assert result["verified"] is True
    assert user.is_verified is True
    assert user.verification_status == "verified"

    get_settings.cache_clear()



def test_verify_user_photo_success_with_openai_client(db_session, monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("NOVITA_API_KEY", "test-key-123")
    monkeypatch.setenv("NOVITA_VISION_MODEL", "qwen/qwen3.6-27b")

    user = register_user(
        db_session,
        UserCreate(
            email="verified@example.com",
            password="Password123!",
            display_name="Verified User",
            accepted_terms=True,
            phone_number="5000000012"
        )
    )
    user.photo_url = "http://example.com/main.jpg"
    db_session.commit()

    # Mock OpenAI client
    mock_choice = MagicMock()
    mock_choice.message.content = '{"is_same_person": true, "confidence": 0.98, "reason": "Yüz hatları birebir örtüşüyor."}'
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_openai_instance = MagicMock()
    mock_openai_instance.chat.completions.create.return_value = mock_response

    monkeypatch.setattr("app.services.vision_verification_service.OpenAI", lambda **kwargs: mock_openai_instance)

    result = verify_user_photo_with_vision(db_session, user, "http://example.com/selfie.jpg")
    assert result["verified"] is True
    assert user.is_verified is True
    assert user.verification_status == "verified"
    assert "Mavi Tik" in result["message"]

    get_settings.cache_clear()


def test_verify_user_photo_rejected_with_openai_client(db_session, monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("NOVITA_API_KEY", "test-key-123")
    monkeypatch.setenv("NOVITA_VISION_MODEL", "qwen/qwen3.6-27b")

    user = register_user(
        db_session,
        UserCreate(
            email="rejected@example.com",
            password="Password123!",
            display_name="Rejected User",
            accepted_terms=True,
            phone_number="5000000013"
        )
    )
    user.photo_url = "http://example.com/main.jpg"
    db_session.commit()

    # Mock OpenAI client returning rejected
    mock_choice = MagicMock()
    mock_choice.message.content = '{"is_same_person": false, "confidence": 0.2, "reason": "Farklı kişi tespit edildi."}'
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_openai_instance = MagicMock()
    mock_openai_instance.chat.completions.create.return_value = mock_response

    monkeypatch.setattr("app.services.vision_verification_service.OpenAI", lambda **kwargs: mock_openai_instance)

    result = verify_user_photo_with_vision(db_session, user, "http://example.com/selfie.jpg")
    assert result["verified"] is False
    assert user.is_verified is False
    assert user.verification_status == "rejected"
    assert "Farklı kişi tespit edildi" in result["message"]

    get_settings.cache_clear()


def test_verify_photo_router_endpoint(client: TestClient, auth_headers: dict[str, str], monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("NOVITA_API_KEY", "")

    # Set photo_url for current user via endpoint
    client.patch("/users/me", headers=auth_headers, json={"bio": "Testing photo verify"})

    response = client.post(
        "/users/me/verify-photo",
        headers=auth_headers,
        json={"selfie_photo_url": "http://127.0.0.1:8000/media/selfie.jpg"}
    )
    
    assert response.status_code == 200
    assert "verified" in response.json()

    get_settings.cache_clear()
