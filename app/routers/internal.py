from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_scraper_api_key
from app.database import get_db
from app.schemas.event_ingestion import EventIngestBatch, EventIngestResult, KnownExternalIds
from app.services.event_ingestion_service import get_known_external_ids, ingest_events

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post(
    "/events/ingest",
    response_model=EventIngestResult,
    dependencies=[Depends(require_scraper_api_key)],
)
def ingest_event_batch(batch: EventIngestBatch, db: Session = Depends(get_db)) -> EventIngestResult:
    return ingest_events(db, batch)


@router.get(
    "/events/known-ids",
    response_model=KnownExternalIds,
    dependencies=[Depends(require_scraper_api_key)],
)
def get_known_ids(source: str, db: Session = Depends(get_db)) -> KnownExternalIds:
    return KnownExternalIds(external_ids=get_known_external_ids(db, source))
