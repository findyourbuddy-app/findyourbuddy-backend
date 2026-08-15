from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.event import Event
from app.schemas.event_ingestion import EventIngestBatch, EventIngestPayload, EventIngestResult


def _find_existing_event(db: Session, source: str, external_id: str) -> Event | None:
    return (
        db.query(Event)
        .filter(Event.source == source, Event.external_id == external_id)
        .first()
    )


def _apply_ingest_payload(event: Event, payload: EventIngestPayload) -> None:
    event.title = payload.title
    event.description = payload.description
    event.category = payload.category
    event.location_name = payload.location_name
    event.latitude = payload.latitude
    event.longitude = payload.longitude
    event.starts_at = payload.starts_at
    event.source_url = payload.source_url
    event.image_url = payload.image_url
    event.is_paid = payload.is_paid


def ingest_events(db: Session, batch: EventIngestBatch) -> EventIngestResult:
    allowed_categories = set(get_settings().allowed_event_categories)
    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    for payload in batch.events:
        if payload.category not in allowed_categories:
            skipped += 1
            errors.append(
                f"{payload.source}:{payload.external_id} - invalid category '{payload.category}'"
            )
            continue

        existing = _find_existing_event(db, payload.source, payload.external_id)
        if existing is None:
            event = Event(source=payload.source, external_id=payload.external_id, creator_id=None)
            _apply_ingest_payload(event, payload)
            db.add(event)
            created += 1
        else:
            _apply_ingest_payload(existing, payload)
            updated += 1

    db.commit()
    return EventIngestResult(created=created, updated=updated, skipped=skipped, errors=errors)
