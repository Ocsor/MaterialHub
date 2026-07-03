"""Read-only REST API consumed by internal applications."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Material
from ..schemas import MaterialResponse

router = APIRouter(prefix="/api/materials", tags=["materials-api"])


def _ordered_query():
    # Blank friendly names sort as absent, after sort_order and before name.
    friendly = func.nullif(func.trim(Material.friendly_name), "")
    return select(Material).order_by(Material.sort_order, case((friendly.is_(None), 1), else_=0), friendly, Material.name)


@router.get("", response_model=list[MaterialResponse])
def active_materials(db: Session = Depends(get_db)):
    return db.scalars(_ordered_query().where(Material.active.is_(True))).all()


@router.get("/all", response_model=list[MaterialResponse])
def all_materials(db: Session = Depends(get_db)):
    return db.scalars(_ordered_query()).all()


@router.get("/{material_id}", response_model=MaterialResponse)
def material_detail(material_id: int, db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return material
