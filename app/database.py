from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    # Supabase's pooler silently drops idle connections; without this,
    # SQLAlchemy hands out a dead connection and every request fails with
    # "SSL SYSCALL error: EOF detected" until the pool happens to cycle it
    # out. pre_ping tests the connection before use and transparently
    # reconnects instead.
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
