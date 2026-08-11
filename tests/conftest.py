from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.notifications import get_notification_sender
from app.database import Base, get_db
from app.main import app


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
        json={"email": "ada@example.com", "password": "s3cret-pass", "display_name": "Ada"},
    )
    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "s3cret-pass"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
