from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_scraper_api_key
from app.database import get_db
from app.schemas.event_ingestion import EventIngestBatch, EventIngestResult
from app.services.event_ingestion_service import ingest_events

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post(
    "/events/ingest",
    response_model=EventIngestResult,
    dependencies=[Depends(require_scraper_api_key)],
)
def ingest_event_batch(batch: EventIngestBatch, db: Session = Depends(get_db)) -> EventIngestResult:
    return ingest_events(db, batch)
