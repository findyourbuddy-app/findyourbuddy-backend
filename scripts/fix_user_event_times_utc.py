"""One-off data migration: shift user-created events' `starts_at` back by the
Turkey offset (UTC+3).

Why: the old `CreateEventScreen` sent the picked time as a naive local
wall-clock string (no `Z`). The backend stores naive datetimes as UTC and the
app reads them back as UTC, so every user-created event ended up 3 hours late
(and early-evening events rolled to the next day). New events are fixed at the
source; this corrects the rows created before that fix.

Scope: only `creator_id IS NOT NULL` events (user-created). Scraped/official
events (`creator_id IS NULL`) are corrected automatically on the next scrape
cycle and are left untouched here.

Run ONCE, right after deploying the CreateEventScreen + EventCreate validator
fix. Running it twice double-shifts the data.

Usage:
    uv run python scripts/fix_user_event_times_utc.py            # dry run
    uv run python scripts/fix_user_event_times_utc.py --apply    # write changes
"""

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models.event import Event

TURKEY_OFFSET = timedelta(hours=3)


def main(apply: bool) -> None:
    session = SessionLocal()
    try:
        events = (
            session.query(Event)
            .filter(Event.creator_id.isnot(None))
            .order_by(Event.id)
            .all()
        )
        if not events:
            print("No user-created events found. Nothing to do.")
            return

        print(f"{'APPLYING' if apply else 'DRY RUN'} -- {len(events)} user-created events\n")
        for event in events:
            new_start = event.starts_at - TURKEY_OFFSET
            safe_title = event.title[:40].encode("ascii", "replace").decode()
            print(f"  #{event.id:<5} {event.starts_at}  ->  {new_start}   {safe_title}")
            if apply:
                event.starts_at = new_start

        if apply:
            session.commit()
            print(f"\nDone. Shifted {len(events)} events back by 3 hours.")
        else:
            print(f"\nDry run only. Re-run with --apply to write {len(events)} changes.")
    finally:
        session.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
