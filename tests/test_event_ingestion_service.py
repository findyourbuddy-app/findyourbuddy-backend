from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.event import Event
from app.schemas.event_ingestion import EventIngestBatch, EventIngestPayload
from app.services.event_ingestion_service import ingest_events


@pytest.fixture(autouse=True)
def _no_real_llm_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests assert on invalid-category handling, not on what a real
    LLM happens to classify a fake title as -- without this, whether an
    invalid category gets "rescued" into a real one depends on whether
    NOVITA_API_KEY is set in whatever environment the test runs in (a real,
    billed network call locally; empty/skipped in CI), making the test
    non-deterministic. Force the "couldn't classify" fallback every time."""
    import app.services.event_ingestion_service as ingestion_module

    monkeypatch.setattr(ingestion_module, "auto_classify_event_category_with_llm", lambda *a, **k: "other")


def _payload(**overrides: object) -> EventIngestPayload:
    defaults: dict[str, object] = {
        "external_id": "evt-1",
        "source": "biletix",
        "title": "Trail run",
        "category": "running",
        "location_name": "Central Park",
        "latitude": 40.0,
        "longitude": -73.0,
        "starts_at": datetime.utcnow() + timedelta(days=1),
    }
    defaults.update(overrides)
    return EventIngestPayload(**defaults)


def test_ingest_creates_new_event(db_session: Session) -> None:
    result = ingest_events(db_session, EventIngestBatch(events=[_payload()]))

    assert result.created == 1
    assert result.updated == 0
    assert result.skipped == 0
    assert result.errors == []

    event = db_session.query(Event).filter(Event.external_id == "evt-1").one()
    assert event.source == "biletix"
    assert event.creator_id is None
    assert event.title == "Trail run"


def test_ingest_stores_image_url(db_session: Session) -> None:
    ingest_events(
        db_session,
        EventIngestBatch(events=[_payload(image_url="https://example.com/evt-1.jpg")]),
    )

    event = db_session.query(Event).filter(Event.external_id == "evt-1").one()
    assert event.image_url == "https://example.com/evt-1.jpg"


def test_ingest_updates_existing_event_with_same_source_and_external_id(
    db_session: Session,
) -> None:
    ingest_events(db_session, EventIngestBatch(events=[_payload(title="Trail run")]))

    result = ingest_events(
        db_session, EventIngestBatch(events=[_payload(title="Trail run (updated)")])
    )

    assert result.created == 0
    assert result.updated == 1
    events = db_session.query(Event).filter(Event.external_id == "evt-1").all()
    assert len(events) == 1
    assert events[0].title == "Trail run (updated)"


def test_ingest_skips_invalid_category(db_session: Session) -> None:
    result = ingest_events(
        db_session, EventIngestBatch(events=[_payload(category="not-a-real-category")])
    )

    assert result.created == 0
    assert result.skipped == 1
    assert len(result.errors) == 1
    assert db_session.query(Event).count() == 0


def test_ingest_continues_batch_after_invalid_record(db_session: Session) -> None:
    batch = EventIngestBatch(
        events=[
            _payload(external_id="bad", category="not-a-real-category"),
            _payload(external_id="good"),
        ]
    )

    result = ingest_events(db_session, batch)

    assert result.skipped == 1
    assert result.created == 1
    assert db_session.query(Event).filter(Event.external_id == "good").one() is not None
