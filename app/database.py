"""Database engine and request-scoped session helpers."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'materials.db'}"

# check_same_thread=False is required because FastAPI may use different worker
# threads for a request. Sessions themselves are still created per request.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class shared by all database models."""


def add_missing_material_columns() -> None:
    """Add local enrichment columns to databases created by older versions."""
    existing = {column["name"] for column in inspect(engine).get_columns("materials")}
    additions = {
        "keywords": "TEXT",
        "primary_cutter": "TEXT",
        "primary_tool": "TEXT",
        "tool_tips": "TEXT",
    }
    with engine.begin() as connection:
        for name, column_type in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE materials ADD COLUMN {name} {column_type}"))


def get_db() -> Generator[Session, None, None]:
    """Provide one SQLAlchemy session and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
