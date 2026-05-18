"""
FastAPI dependency injection utilities.
"""

from typing import Generator

from sqlalchemy.orm import Session

from data.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for FastAPI route handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
