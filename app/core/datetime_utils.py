from datetime import datetime, timezone


def utcnow() -> datetime:
    """Returns current UTC time as a naive datetime.

    SQLAlchemy DateTime columns (without timezone=True) store and return
    naive datetimes. Use this function for Python-level comparisons with
    database-backed datetime fields to avoid offset-naive vs offset-aware
    TypeError when running against SQLite (tests) or PostgreSQL without
    timestamptz columns.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
