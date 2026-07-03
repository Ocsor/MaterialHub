"""Administrator-facing material list and edit routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..main_paths import TEMPLATES_DIR
from ..models import Material

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/materials")
def materials_page(request: Request, q: str = "", kind: str = "all", status: str = "active", db: Session = Depends(get_db)):
    statement = select(Material)
    if q.strip():
        # Match every word independently, but allow each word to occur in any
        # searchable field. This makes word order irrelevant: "Acrylic Gloss
        # Clear" will match "Acrylic Clear Gloss XT_5mm".
        word_matches = []
        for word in q.split():
            term = f"%{word}%"
            word_matches.append(or_(
                Material.name.ilike(term), Material.friendly_name.ilike(term), Material.sku.ilike(term),
                Material.supplier_name.ilike(term), Material.matex.ilike(term),
                Material.prepit.ilike(term), Material.imp.ilike(term),
            ))
        statement = statement.where(and_(*word_matches))
    if kind == "sheets":
        statement = statement.where(Material.size_type == r"App\Models\Sheet")
    elif kind == "rolls":
        statement = statement.where(Material.size_type == r"App\Models\Roll")
    if status == "active":
        statement = statement.where(Material.active.is_(True))
    elif status == "inactive":
        statement = statement.where(Material.active.is_(False))
    rows = db.scalars(statement.order_by(Material.sort_order, Material.friendly_name, Material.name)).all()
    return templates.TemplateResponse(request, "materials.html", {"materials": rows, "q": q, "kind": kind, "status": status})


@router.get("/materials/{material_id}/edit")
def edit_page(material_id: int, request: Request, db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return templates.TemplateResponse(request, "edit_material.html", {"material": material})


@router.post("/materials/{material_id}/edit")
def save_material(
    material_id: int,
    friendly_name: Annotated[str, Form()] = "", matex: Annotated[str, Form()] = "",
    prepit: Annotated[str, Form()] = "", imp: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    for field, value in {"friendly_name": friendly_name, "matex": matex, "prepit": prepit, "imp": imp, "notes": notes}.items():
        setattr(material, field, value.strip() or None)
    db.commit()
    return RedirectResponse("/materials", status_code=303)


@router.post("/materials/{material_id}/inline")
def save_material_inline(
    material_id: int,
    matex: Annotated[str, Form()] = "",
    prepit: Annotated[str, Form()] = "",
    imp: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    """Save the small set of local fields exposed directly in the table."""
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    material.matex = matex.strip() or None
    # Text storage is retained for backwards compatibility; "1" represents on.
    material.prepit = "1" if prepit else None
    material.imp = "1" if imp else None
    db.commit()
    return RedirectResponse("/materials", status_code=303)
