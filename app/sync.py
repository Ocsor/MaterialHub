"""Synchronise remote stock into the local material catalogue."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import Material
from .stocktopus_client import StocktopusClient

ALLOWED_SIZE_TYPES = {r"App\Models\Sheet", r"App\Models\Roll"}

# Canonical Matex values used only when a material is first imported. Matching
# is case-insensitive, while these spellings are what get stored locally.
MATEX_NAME_KEYWORDS = ("White", "Black", "Clear", "Opal", "MDF", "Plywood", "Slate", "Frosted")


@dataclass
class SyncResult:
    downloaded: int = 0
    imported: int = 0
    updated: int = 0
    deactivated: int = 0


def _value(item: dict[str, Any], key: str, nested: str | None = None) -> Any:
    """Read either a flat API field or a common nested relationship's name."""
    value = item.get(key)
    if value is None and nested and isinstance(item.get(nested), dict):
        value = item[nested].get("name")
    return value


def _remote_fields(item: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Map Stocktopus JSON to only the fields that Stocktopus controls."""
    stock_id = item.get("id")
    if stock_id is None:
        raise ValueError("A Stocktopus stock record was missing its id.")
    size = item.get("size") if isinstance(item.get("size"), dict) else {}
    return {
        "stocktopus_id": str(stock_id),
        "name": str(item.get("name") or ""),
        "sku": item.get("sku"),
        "material_group": _value(item, "material_group", "group"),
        "material_type": _value(item, "material_type", "type"),
        "size_type": item.get("size_type"),
        "width_mm": item.get("width_mm") or item.get("width") or size.get("width"),
        "height_mm": item.get("height_mm") or item.get("height") or size.get("height"),
        "length_mm": item.get("length_mm") or item.get("length") or size.get("length"),
        "thickness_mm": item.get("thickness_mm") or item.get("thickness") or size.get("thickness"),
        "size_unit": item.get("size_unit") or size.get("unit"),
        "size_string": item.get("size_string") or size.get("label"),
        "quantity": item.get("quantity"),
        "price_range": str(item["price_range"]) if item.get("price_range") is not None else None,
        "supplier_name": _value(item, "supplier_name", "supplier"),
        "active": bool(item.get("active", True)),
        "raw_stocktopus_json": json.dumps(item, ensure_ascii=False, default=str),
        "last_seen_at": now,
        "updated_from_stocktopus_at": now,
    }


def _initial_local_fields(name: str) -> dict[str, str | None]:
    """Create defaults for local fields on a brand-new material.

    A non-alphanumeric boundary is used instead of ``\b`` so Stocktopus names
    such as ``ACM Black_3mm`` correctly recognise Black next to an underscore.
    Multiple keyword matches are deliberately ambiguous and leave Matex blank.
    """
    matches = [
        keyword
        for keyword in MATEX_NAME_KEYWORDS
        if re.search(
            rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])",
            name,
            flags=re.IGNORECASE,
        )
    ]
    return {
        "friendly_name": name,
        "matex": matches[0] if len(matches) == 1 else None,
    }


async def synchronise_materials(db: Session, client: StocktopusClient | None = None) -> SyncResult:
    """Download, upsert, and deactivate materials in one transaction."""
    stock = await (client or StocktopusClient()).fetch_all_stock()
    result = SyncResult(downloaded=len(stock))
    now = datetime.now(timezone.utc)
    existing = {m.stocktopus_id: m for m in db.scalars(select(Material)).all()}
    seen: set[str] = set()

    try:
        for item in stock:
            if item.get("size_type") not in ALLOWED_SIZE_TYPES:
                continue
            fields = _remote_fields(item, now)
            stock_id = fields["stocktopus_id"]
            seen.add(stock_id)
            material = existing.get(stock_id)
            if material is None:
                db.add(
                    Material(
                        **fields,
                        **_initial_local_fields(fields["name"]),
                        first_seen_at=now,
                    )
                )
                result.imported += 1
            else:
                for field, value in fields.items():
                    setattr(material, field, value)
                result.updated += 1

        # Only records once imported from Stocktopus are affected; nothing is deleted.
        stale = set(existing) - seen
        if stale:
            result.deactivated = db.execute(
                update(Material).where(Material.stocktopus_id.in_(stale), Material.active.is_(True)).values(active=False)
            ).rowcount
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result
