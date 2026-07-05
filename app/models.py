"""Persistent database models."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Material(Base):
    """A Stocktopus material plus fields owned exclusively by MaterialHub."""

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    stocktopus_id: Mapped[str] = mapped_column(Text, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, default="")
    sku: Mapped[str | None] = mapped_column(Text)
    material_group: Mapped[str | None] = mapped_column(Text)
    material_type: Mapped[str | None] = mapped_column(Text)
    size_type: Mapped[str] = mapped_column(Text, index=True)
    width_mm: Mapped[float | None] = mapped_column(Float)
    height_mm: Mapped[float | None] = mapped_column(Float)
    length_mm: Mapped[float | None] = mapped_column(Float)
    thickness_mm: Mapped[float | None] = mapped_column(Float)
    size_unit: Mapped[str | None] = mapped_column(Text)
    size_string: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[float | None] = mapped_column(Float)
    price_range: Mapped[str | None] = mapped_column(Text)
    supplier_name: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    raw_stocktopus_json: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_from_stocktopus_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # These columns belong to MaterialHub and sync.py deliberately never updates them.
    friendly_name: Mapped[str | None] = mapped_column(Text)
    matex: Mapped[str | None] = mapped_column(Text)
    prepit: Mapped[str | None] = mapped_column(Text)
    imp: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[str | None] = mapped_column(Text)
    primary_cutter: Mapped[str | None] = mapped_column(Text)
    primary_tool: Mapped[str | None] = mapped_column(Text)
    tool_tips: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
