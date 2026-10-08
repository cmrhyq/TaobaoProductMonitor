"""
SQLAlchemy engine and session factory.
"""

from collections.abc import Generator
from contextlib import contextmanager

import structlog
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from config.settings import PROJECT_ROOT, get_settings

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


def _migrate_schema() -> None:
    """Lightweight auto-migration for pre-existing databases.

    create_all() only creates missing tables; existing tables need explicit
    ALTERs to pick up new columns.
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        if engine.url.get_backend_name() == "sqlite":
            columns = conn.execute(text("PRAGMA table_info(price_history)")).fetchall()
            if columns and not any(row[1] == "original_price" for row in columns):
                conn.execute(text("ALTER TABLE price_history ADD COLUMN original_price REAL"))
                conn.commit()
                logger.info("Added price_history.original_price column")
        else:
            exists = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'price_history' "
                    "AND COLUMN_NAME = 'original_price'"
                )
            ).scalar()
            if not exists:
                conn.execute(
                    text(
                        "ALTER TABLE price_history ADD COLUMN original_price "
                        "DECIMAL(10, 2) NULL COMMENT '优惠前挂牌价，检测到补贴/促销价时记录'"
                    )
                )
                conn.commit()
                logger.info("Added price_history.original_price column")


def init_db():
    """Create all tables if they don't exist."""
    from data.models import Base
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    logger.info("Database tables initialized", url=DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL)
