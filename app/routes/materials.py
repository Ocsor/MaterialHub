"""Administrator-facing material list and edit routes."""

import csv
import json
import os
from io import BytesIO, StringIO
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlencode
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..main_paths import PREPIT_TEMPLATE_RULES_PATH, PREPIT_TEMPLATES_DIR, ROOT_DIR, TEMPLATES_DIR
from ..models import Material
from ..prepit_export import PrepitExportError, build_prepit_xml, prepit_media_name

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory=TEMPLATES_DIR)

IMP_CSV_COLUMNS = [
    "Grade name",
    "Paper weight",
    "Caliper",
    "Cost",
    "Width/Grain",
    "Height",
    "Location",
    "Inventory",
    "Sheet size on order",
    "Allowed folding depth",
    "Requires UV drying",
    "Different back finish",
    "Cost per sheet",
    "Mill",
]

# This allow-list mirrors Reference/Requested.txt. Nested mappings keep useful
# business data while excluding Stocktopus's internal IDs and metadata.
STOCKTOPUS_VISIBLE_FIELDS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("sku", None),
    ("quantity", None),
    ("name", None),
    ("material_group", None),
    ("material_type", None),
    ("size", ("width", "height", "thickness")),
    ("stock_prices", ("price", "supplier_ref")),
    ("supplier", ("name", "rep", "rep_phone", "rep_email", "email", "phone", "account_type")),
)


def _display_value(value: Any) -> str:
    """Format a scalar Stocktopus value consistently for the details panel."""
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _display_field(name: str, value: Any) -> dict[str, str]:
    return {
        "name": "Thick" if name == "thickness" else name.replace("_", " ").title(),
        "source_name": name,
        "value": _display_value(value),
    }


def _stocktopus_fields(material: Material) -> list[dict[str, Any]]:
    """Prepare the requested Stocktopus fields as individually styled values."""
    try:
        payload = json.loads(material.raw_stocktopus_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []

    fields = []
    for name, nested_fields in STOCKTOPUS_VISIBLE_FIELDS:
        value = payload.get(name)
        if nested_fields is None:
            fields.append({"kind": "value", **_display_field(name, value)})
        elif isinstance(value, list):
            items = [
                [_display_field(child, item.get(child)) for child in nested_fields]
                for item in value
                if isinstance(item, dict)
            ]
            fields.append({
                "kind": "collection",
                "name": name.replace("_", " ").title(),
                "source_name": name,
                "items": items,
            })
        else:
            nested_value = value if isinstance(value, dict) else {}
            fields.append({
                "kind": "group",
                "name": name.replace("_", " ").title(),
                "source_name": name,
                "children": [_display_field(child, nested_value.get(child)) for child in nested_fields],
            })
    return fields


def _adjacent_material_ids(db: Session, material_id: int) -> tuple[int | None, int | None]:
    """Return the previous and next IDs in the administrator list order."""
    ordered_ids = list(db.scalars(
        select(Material.id).order_by(
            Material.sort_order,
            Material.friendly_name,
            Material.name,
            Material.id,
        )
    ))
    try:
        position = ordered_ids.index(material_id)
    except ValueError:
        return None, None
    previous_id = ordered_ids[position - 1] if position > 0 else None
    next_id = ordered_ids[position + 1] if position + 1 < len(ordered_ids) else None
    return previous_id, next_id


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
                Material.keywords.ilike(term), Material.primary_cutter.ilike(term),
                Material.primary_tool.ilike(term), Material.tool_tips.ilike(term),
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
    return templates.TemplateResponse(request, "materials.html", {
        "materials": rows,
        "q": q,
        "kind": kind,
        "status": status,
        "prepit_copy_name": _prepit_copy_name,
    })


@router.get("/materials/download/prepit")
def download_prepit_zip(db: Session = Depends(get_db)):
    rows = _prepit_rows(db)
    if not rows:
        return RedirectResponse("/materials?error=No%20Prepit%20materials%20are%20checked", status_code=303)

    try:
        archive = _prepit_zip(rows)
    except PrepitExportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    archive.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="prepit_xml.zip"'}
    return StreamingResponse(archive, media_type="application/zip", headers=headers)


@router.get("/materials/download/imp")
def download_imp_csv(db: Session = Depends(get_db)):
    rows = _imp_rows(db)
    if not rows:
        return RedirectResponse("/materials?error=No%20IMP%20materials%20are%20checked", status_code=303)

    output = _imp_csv(rows)
    headers = {"Content-Disposition": 'attachment; filename="imp_materials.csv"'}
    return Response(content=output.getvalue(), media_type="text/csv", headers=headers)


@router.post("/materials/export")
def export_material_files(db: Session = Depends(get_db)):
    export_path = _export_path()
    prepit_rows = _prepit_rows(db)
    imp_rows = _imp_rows(db)

    try:
        export_path.mkdir(parents=True, exist_ok=True)
        (export_path / "prepit_xml.zip").write_bytes(_prepit_zip(prepit_rows).getvalue())
        (export_path / "imp_materials.csv").write_text(_imp_csv(imp_rows).getvalue(), encoding="utf-8", newline="")
        (export_path / "prepit_rolls.txt").write_text(
            _prepit_name_list(prepit_rows, roll=True),
            encoding="utf-8",
            newline="",
        )
        (export_path / "prepit_sheets.txt").write_text(
            _prepit_name_list(prepit_rows, roll=False),
            encoding="utf-8",
            newline="",
        )
    except PrepitExportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    query = urlencode({"notice": f"Exported files to {export_path}"})
    return RedirectResponse(f"/materials?{query}", status_code=303)


def _prepit_rows(db: Session) -> list[Material]:
    return list(db.scalars(
        select(Material)
        .where(Material.active.is_(True), Material.prepit.is_not(None))
        .order_by(Material.sort_order, Material.friendly_name, Material.name, Material.id)
    ))


def _imp_rows(db: Session) -> list[Material]:
    return list(db.scalars(
        select(Material)
        .where(Material.active.is_(True), Material.imp.is_not(None))
        .order_by(Material.sort_order, Material.friendly_name, Material.name, Material.id)
    ))


def _prepit_zip(rows: list[Material]) -> BytesIO:
    archive = BytesIO()
    used_filenames: set[str] = set()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
        for material in rows:
            generated = build_prepit_xml(material, PREPIT_TEMPLATES_DIR, PREPIT_TEMPLATE_RULES_PATH)
            filename = _unique_zip_filename(generated.filename, used_filenames)
            zip_file.writestr(filename, generated.content)
    archive.seek(0)
    return archive


def _imp_csv(rows: list[Material]) -> StringIO:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=IMP_CSV_COLUMNS)
    writer.writeheader()
    for material in rows:
        writer.writerow(_imp_csv_row(material))
    return output


def _prepit_name_list(rows: list[Material], roll: bool) -> str:
    names = [_prepit_list_name(material) for material in rows if _is_roll_material(material) is roll]
    return "\n".join(names) + ("\n" if names else "")


def _prepit_list_name(material: Material) -> str:
    return prepit_media_name(material)


def _prepit_copy_name(material: Material) -> str:
    try:
        return prepit_media_name(material)
    except PrepitExportError:
        return ""


def _export_path() -> Path:
    configured_path = os.getenv("MATERIALHUB_EXPORT_PATH", "").strip()
    if not configured_path:
        raise HTTPException(status_code=500, detail="MATERIALHUB_EXPORT_PATH is not set in .env")
    path = Path(configured_path).expanduser()
    return path if path.is_absolute() else ROOT_DIR / path


def _imp_csv_row(material: Material) -> dict[str, str]:
    is_roll = _is_roll_material(material)
    return {
        "Grade name": _imp_grade_name(material, is_roll),
        "Paper weight": "0",
        "Caliper": "0.1" if is_roll else _format_csv_number(material.thickness_mm),
        "Cost": "8a",
        "Width/Grain": _format_csv_number(material.width_mm),
        "Height": "" if is_roll else _format_csv_number(material.height_mm),
        "Location": "",
        "Inventory": "",
        "Sheet size on order": "",
        "Allowed folding depth": "",
        "Requires UV drying": "",
        "Different back finish": "",
        "Cost per sheet": "",
        "Mill": material.supplier_name or "",
    }


def _imp_grade_name(material: Material, is_roll: bool) -> str:
    sku = (material.sku or "").strip()
    name = ((material.friendly_name or material.name) or "").strip()
    width = _format_csv_number(material.width_mm)
    if is_roll:
        return "_".join(part for part in [sku, name, width] if part)
    height = _format_csv_number(material.height_mm)
    size = f"{width}x{height}mm" if width or height else ""
    return "_".join(part for part in [sku, name, size] if part)


def _format_csv_number(value: float | None) -> str:
    if value is None:
        return ""
    return str(int(value)) if value == int(value) else f"{value:g}"


def _is_roll_material(material: Material) -> bool:
    return (material.material_type or "").casefold() == "roll" or material.size_type.endswith(r"\Roll")


def _unique_zip_filename(filename: str, used_filenames: set[str]) -> str:
    if filename not in used_filenames:
        used_filenames.add(filename)
        return filename
    stem, suffix = filename.rsplit(".", 1)
    counter = 2
    while True:
        candidate = f"{stem}_{counter}.{suffix}"
        if candidate not in used_filenames:
            used_filenames.add(candidate)
            return candidate
        counter += 1


@router.get("/materials/{material_id}/edit")
def edit_page(material_id: int, request: Request, db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    previous_id, next_id = _adjacent_material_ids(db, material_id)
    return templates.TemplateResponse(request, "edit_material.html", {
        "material": material,
        "stocktopus_fields": _stocktopus_fields(material),
        "previous_id": previous_id,
        "next_id": next_id,
    })


@router.post("/materials/{material_id}/edit")
def save_material(
    material_id: int,
    friendly_name: Annotated[str, Form()] = "", matex: Annotated[str, Form()] = "",
    prepit: Annotated[str, Form()] = "", imp: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    keywords: Annotated[str, Form()] = "",
    primary_cutter: Annotated[str, Form()] = "",
    primary_tool: Annotated[str, Form()] = "",
    tool_tips: Annotated[str, Form()] = "",
    navigation: Annotated[str, Form()] = "save",
    db: Session = Depends(get_db),
):
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    if primary_cutter not in {"", "CNC", "JWEI", "Laser"}:
        raise HTTPException(status_code=422, detail="Invalid primary cutter")
    if primary_cutter not in {"CNC", "JWEI"}:
        primary_tool = ""
    fields = {
        "friendly_name": friendly_name, "matex": matex, "prepit": prepit,
        "imp": imp, "notes": notes, "keywords": keywords,
        "primary_cutter": primary_cutter, "primary_tool": primary_tool,
        "tool_tips": tool_tips,
    }
    for field, value in fields.items():
        setattr(material, field, value.strip() or None)
    db.commit()

    # Navigation is resolved after saving, so every button safely preserves the
    # current form before moving away from it.
    previous_id, next_id = _adjacent_material_ids(db, material_id)
    if navigation == "previous" and previous_id is not None:
        return RedirectResponse(f"/materials/{previous_id}/edit", status_code=303)
    if navigation == "next" and next_id is not None:
        return RedirectResponse(f"/materials/{next_id}/edit", status_code=303)
    return RedirectResponse("/materials", status_code=303)


@router.post("/materials/{material_id}/inline")
def save_material_inline(
    material_id: int,
    request: Request,
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
    if request.headers.get("X-Requested-With") == "fetch":
        return Response(status_code=204)
    return RedirectResponse(request.headers.get("referer", "/materials"), status_code=303)
