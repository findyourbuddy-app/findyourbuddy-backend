"""One-off cleanup: delete scraped events whose `starts_at` was fabricated by a
one-time bulk import (every such row shares second=52, microsecond=606984 --
a single `datetime.utcnow()` captured once, then `+ timedelta(...)` per event).

Etkinlik.io's `start_r001` is a real UTC timestamp; the live scraper (with the
`_parse_starts_at` fix) ingests correct times. But the scheduler skips events it
already knows, so these bad rows never self-correct. Deleting them frees their
external_ids so the next scrape re-fetches them with real start times.

Safe: verified 0 of these have any Match / EventAttendance / Swipe / Bookmark.

Usage:
    uv run python scripts/purge_fabricated_scraped_events.py           # dry run
    uv run python scripts/purge_fabricated_scraped_events.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func

from app.database import SessionLocal
from app.models.bookmark import Bookmark
from app.models.event import Event
from app.models.event_attendance import EventAttendance
from app.models.match import Match
from app.models.notification import Notification
from app.models.swipe import Swipe

FABRICATED_SECOND = 52
FABRICATED_MICROSECOND = 606984


def main(apply: bool) -> None:
    session = SessionLocal()
    try:
        events = (
            session.query(Event)
            .filter(Event.creator_id.is_(None))
            .all()
        )
        target_ids = [
            e.id
            for e in events
            if e.starts_at.second == FABRICATED_SECOND
            and e.starts_at.microsecond == FABRICATED_MICROSECOND
        ]
        if not target_ids:
            print("No fabricated scraped events found. Nothing to do.")
            return

        blocked = session.query(func.count(func.distinct(Match.event_id))).filter(
            Match.event_id.in_(target_ids)
        ).scalar()
        if blocked:
            print(f"ABORT: {blocked} of these events have a Match -- refusing to delete.")
            return

        print(f"{'APPLYING' if apply else 'DRY RUN'} -- {len(target_ids)} fabricated scraped events")
        if not apply:
            print("Re-run with --apply to delete them (and re-run the scraper afterwards).")
            return

        session.query(Swipe).filter(Swipe.event_id.in_(target_ids)).delete(synchronize_session=False)
        session.query(Bookmark).filter(Bookmark.event_id.in_(target_ids)).delete(synchronize_session=False)
        session.query(EventAttendance).filter(EventAttendance.event_id.in_(target_ids)).delete(
            synchronize_session=False
        )
        session.query(Notification).filter(Notification.event_id.in_(target_ids)).update(
            {Notification.event_id: None}, synchronize_session=False
        )
        session.query(Event).filter(Event.id.in_(target_ids)).delete(synchronize_session=False)
        session.commit()
        print(f"Deleted {len(target_ids)} events. Run the scraper to re-populate with real times.")
    finally:
        session.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
