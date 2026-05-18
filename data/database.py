"""
SQLAlchemy engine and session factory.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

import structlog

from config.settings import get_settings, PROJECT_ROOT

logger = structlog.get_logger(__name__)


def _build_database_url() -> str:
    settings = get_settings()
    if settings.db.type == "sqlite":
        from pathlib import Path
        path = Path(settings.db.sqlite_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"
    return (
        f"mysql+pymysql://{settings.db.mysql_user}:{settings.db.mysql_password}"
        f"@{settings.db.mysql_host}:{settings.db.mysql_port}/{settings.db.mysql_database}"
        f"?charset=utf8mb4"
    )


DATABASE_URL = _build_database_url()

_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional session scope."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Create all tables if they don't exist."""
    from data.models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized", url=DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL)
