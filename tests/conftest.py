from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.notifications import get_notification_sender
from app.core.rate_limit import limiter
from app.database import Base, get_db
from app.main import app
import app.core.email as email_module
import app.core.password_reset as password_reset_module
import app.services.llm_moderation_service as llm_moderation_module


class FakeNotificationSender:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str, str]] = []

    def send(self, user_id: int, title: str, body: str) -> None:
        self.sent.append((user_id, title, body))


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def notification_sender() -> FakeNotificationSender:
    return FakeNotificationSender()


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Generator[None, None, None]:
    """Her testten önce sayaçları sıfırlar, testler arası çakışmayı önler."""
    limiter.reset()
    yield


@pytest.fixture(autouse=True)
def _no_real_emails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Several flows (password reset, event moderation approve/reject) send
    real email via the project's live Gmail SMTP account -- without this,
    every test run spams that inbox (and any test address used as a
    recipient). Every email send in the app routes through app.core.email,
    so mocking these two covers all of them."""
    monkeypatch.setattr(password_reset_module, "send_plain_email", lambda *a, **k: True)
    monkeypatch.setattr(email_module, "send_plain_email", lambda *a, **k: True)
    monkeypatch.setattr(email_module, "send_html_email", lambda *a, **k: True)


@pytest.fixture(autouse=True)
def _no_real_llm_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Event creation moderates content and classifies its category through a
    live Novita AI call when NOVITA_API_KEY is set (it is, in this project's
    .env) -- without this, every test that creates an event makes a real,
    slow, non-deterministic network call. Auto-approve with no category
    override reproduces the same behavior the app already falls back to when
    no API key is configured."""
    monkeypatch.setattr(llm_moderation_module, "evaluate_event_with_llm", lambda event: (True, None))
    monkeypatch.setattr(llm_moderation_module, "classify_user_event_category_with_llm", lambda title, description=None: None)


@pytest.fixture()
def client(
    db_session: Session, notification_sender: FakeNotificationSender
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_notification_sender] = lambda: notification_sender
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={
            "email": "ada@example.com",
            "password": "s3cret-pass",
            "display_name": "Ada",
            "accepted_terms": True,
            "phone_number": "5000000001",
        },
    )
    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "s3cret-pass"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
