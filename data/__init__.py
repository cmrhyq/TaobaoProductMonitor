"""
Data layer package.
Provides SQLAlchemy ORM models, database session management, and repositories.
"""

from data.database import get_session, engine, SessionLocal
from data.models import Base
