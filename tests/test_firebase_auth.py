from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@patch("firebase_admin.auth.verify_id_token")
def test_firebase_login_provisions_new_user(mock_verify):
    mock_verify.return_value = {
        "uid": "test_firebase_uid_12345",
        "phone_number": "+905551234567",
        "name": "Firebase User Test",
    }

    res = client.post("/auth/firebase-login", json={"id_token": "valid_mock_firebase_token"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@patch("firebase_admin.auth.verify_id_token")
def test_firebase_login_invalid_token_returns_401(mock_verify):
    mock_verify.side_effect = ValueError("Token expired")

    res = client.post("/auth/firebase-login", json={"id_token": "invalid_token"})
    assert res.status_code == 401
    assert "Geçersiz" in res.json()["detail"]
