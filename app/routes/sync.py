"""Manual synchronisation endpoint for administrators."""

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from ..database import get_db
from ..stocktopus_client import StocktopusError
from ..sync import synchronise_materials

router = APIRouter(tags=["sync"])


@router.post("/sync")
async def run_sync(db: Session = Depends(get_db)):
    try:
        result = await synchronise_materials(db)
        message = f"Sync complete: {result.imported} added, {result.updated} updated, {result.deactivated} inactive"
        return RedirectResponse(f"/materials?{urlencode({'notice': message})}", status_code=303)
    except StocktopusError as exc:
        return RedirectResponse(f"/materials?{urlencode({'error': str(exc)})}", status_code=303)
