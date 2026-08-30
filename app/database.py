from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine_kwargs: dict = {"pool_pre_ping": True}
if "sqlite" in settings.database_url.lower():
    engine_kwargs["connect_args"] = {"timeout": 30, "check_same_thread": False}
else:
    engine_kwargs["pool_size"] = settings.db_pool_size
    engine_kwargs["max_overflow"] = settings.db_max_overflow
    engine_kwargs["pool_timeout"] = settings.db_pool_timeout_s
    engine_kwargs["pool_recycle"] = settings.db_pool_recycle_s
    engine_kwargs["connect_args"] = {
        "connect_timeout": settings.db_connect_timeout_s,
        # server-side caps (ms) so a slow query / lock can't pin a thread forever
        "options": (
            f"-c statement_timeout={settings.db_statement_timeout_ms}"
            f" -c lock_timeout={settings.db_lock_timeout_ms}"
            f" -c idle_in_transaction_session_timeout={settings.db_statement_timeout_ms * 2}"
        ),
        # notice a dead connection instead of blocking on a half-open socket
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }

engine = create_engine(settings.database_url, **engine_kwargs)

if "sqlite" in settings.database_url.lower():
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
