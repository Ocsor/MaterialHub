"""Read-only REST API consumed by internal applications."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Material
from ..schemas import MaterialResponse

router = APIRouter(prefix="/api/materials", tags=["materials-api"])


def _ordered_query():
    # Blank friendly names sort as absent, after sort_order and before name.
    friendly = func.nullif(func.trim(Material.friendly_name), "")
    return select(Material).order_by(Material.sort_order, case((friendly.is_(None), 1), else_=0), friendly, Material.name)


def _display_name_expression():
    """SQL equivalent of MaterialResponse.display_name."""
    return func.coalesce(func.nullif(func.trim(Material.friendly_name), ""), Material.name)


@router.get("", response_model=list[MaterialResponse])
def active_materials(db: Session = Depends(get_db)):
    return db.scalars(_ordered_query().where(Material.active.is_(True))).all()


@router.get("/all", response_model=list[MaterialResponse])
def all_materials(db: Session = Depends(get_db)):
    return db.scalars(_ordered_query()).all()


@router.get("/lookup", response_model=list[MaterialResponse])
def lookup_materials(
    q: str = "",
    kind: Literal["material", "laminate", "all"] = "all",
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return a small, searchable list designed for application lookup fields.

    Search words may appear in any order. ``kind=laminate`` includes records
    classified in the LAMINATE material group or whose display name contains
    "Laminate"; ``kind=material`` excludes them.
    """
    display_name = _display_name_expression()
    statement = _ordered_query().where(Material.active.is_(True))

    laminate_match = or_(
        display_name.ilike("%laminate%"),
        func.upper(func.trim(Material.material_group)) == "LAMINATE",
    )
    if kind == "laminate":
        statement = statement.where(laminate_match)
    elif kind == "material":
        statement = statement.where(~laminate_match)

    if q.strip():
        word_matches = []
        for word in q.split():
            term = f"%{word}%"
            word_matches.append(or_(
                display_name.ilike(term),
                Material.name.ilike(term),
                Material.sku.ilike(term),
                Material.matex.ilike(term),
                Material.keywords.ilike(term),
                Material.primary_cutter.ilike(term),
                Material.primary_tool.ilike(term),
                Material.tool_tips.ilike(term),
            ))
        statement = statement.where(and_(*word_matches))

    return db.scalars(statement.limit(limit)).all()


@router.get("/{material_id}", response_model=MaterialResponse)
def material_detail(material_id: int, db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return material
