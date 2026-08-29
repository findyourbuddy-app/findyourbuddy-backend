"""One-off: bring a DB that is stuck at alembic `e5f6a7b8c9d0` up to head
`e6b0c4a3f2d1` WITHOUT running `alembic upgrade` (which trips over the
merge-point / already-applied notification columns).

Applies the head-path DDL idempotently, then `alembic stamp head`:
  a3c1e8f92b05  -> ix_swipes_swiper_event                (missing here)
  b3d4e5f6a7b8  -> notifications.event_id/match_id/...    (already present)
  d5a9b3f2e1c0  -> event_ratings table                   (missing here)
  e6b0c4a3f2d1  -> drop orphan phone_verification_codes   (present, dropped)

Usage:
    uv run python scripts/sync_schema_to_head.py            # show plan
    uv run python scripts/sync_schema_to_head.py --apply
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import SessionLocal

BACKEND_DIR = Path(__file__).resolve().parent.parent
TARGET_REVISION = "e6b0c4a3f2d1"

STEPS = [
    (
        "ix_swipes_swiper_event index",
        "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_swipes_swiper_event'",
        [
            "CREATE INDEX IF NOT EXISTS ix_swipes_swiper_event ON swipes (swiper_id, event_id)"
        ],
    ),
    (
        "event_ratings table",
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'event_ratings'",
        [
            """
            CREATE TABLE IF NOT EXISTS event_ratings (
                id SERIAL PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
                CONSTRAINT uq_event_ratings_event_user UNIQUE (event_id, user_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_event_ratings_event_id ON event_ratings (event_id)",
            "CREATE INDEX IF NOT EXISTS ix_event_ratings_user_id ON event_ratings (user_id)",
        ],
    ),
    (
        "drop orphan phone_verification_codes",
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'phone_verification_codes'",
        ["DROP TABLE IF EXISTS phone_verification_codes"],
    ),
]


def main(apply: bool) -> None:
    session = SessionLocal()
    try:
        current = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"alembic_version currently: {current}\n")

        for name, check_sql, ddl in STEPS:
            present = session.execute(text(check_sql)).first() is not None
            state = "present" if present else "MISSING"
            print(f"  [{state:>7}] {name}")
            if apply:
                for statement in ddl:
                    session.execute(text(statement))
        if apply:
            session.commit()
    finally:
        session.close()

    if not apply:
        print("\nDry run. Re-run with --apply to run the DDL and stamp head.")
        return

    print(f"\nDDL applied. Stamping alembic head -> {TARGET_REVISION} ...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "stamp", "head"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    result.check_returncode()

    session = SessionLocal()
    try:
        now = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"alembic_version now: {now}")
    finally:
        session.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
