"""Push MaterialHub material data to a configured Google Sheet."""

import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .main_paths import ROOT_DIR
from .models import Material

SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
DEFAULT_SHEET_NAME = "Materials"
HEADERS = ["SKU", "Friendly Name", "Width", "Height", "Thick"]


class GoogleSheetsSyncError(RuntimeError):
    """Raised when the Google Sheets sync cannot be completed."""


def sync_materials_to_google_sheet(db: Session) -> int:
    """Replace the configured sheet tab with the current active material list."""
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
    if not spreadsheet_id:
        raise GoogleSheetsSyncError("GOOGLE_SHEETS_SPREADSHEET_ID is not set in .env")

    sheet_name = os.getenv("GOOGLE_SHEETS_SHEET_NAME", DEFAULT_SHEET_NAME).strip() or DEFAULT_SHEET_NAME
    service = _sheets_service()
    _ensure_sheet_exists(service, spreadsheet_id, sheet_name)

    rows = _material_rows(db)
    values = [HEADERS, *rows]
    range_name = f"{_quote_sheet_name(sheet_name)}!A:E"

    try:
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=range_name,
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{_quote_sheet_name(sheet_name)}!A1",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()
    except Exception as exc:  # Google client raises HttpError, imported lazily.
        raise GoogleSheetsSyncError(_google_error_message(exc)) from exc

    return len(rows)


def _sheets_service() -> Any:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise GoogleSheetsSyncError(
            "Google Sync dependencies are not installed. Run: pip install -r requirements.txt"
        ) from exc

    credentials = _credentials()
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _credentials() -> Any:
    try:
        from google.oauth2 import service_account
    except ImportError as exc:
        raise GoogleSheetsSyncError(
            "Google Sync dependencies are not installed. Run: pip install -r requirements.txt"
        ) from exc

    credentials_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    credentials_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()

    if credentials_json:
        try:
            info = json.loads(credentials_json)
        except json.JSONDecodeError as exc:
            raise GoogleSheetsSyncError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    if credentials_file:
        path = Path(credentials_file).expanduser()
        if not path.is_absolute():
            path = ROOT_DIR / path
        if not path.exists():
            raise GoogleSheetsSyncError(f"Google service account file not found: {path}")
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)

    raise GoogleSheetsSyncError("Set GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON in .env")


def _material_rows(db: Session) -> list[list[str]]:
    friendly = func.nullif(func.trim(Material.friendly_name), "")
    statement = (
        select(Material)
        .where(Material.active.is_(True))
        .order_by(Material.sort_order, case((friendly.is_(None), 1), else_=0), friendly, Material.name)
    )
    return [
        [
            material.sku or "",
            (material.friendly_name or material.name or "").strip(),
            _format_number(material.width_mm),
            _format_number(material.height_mm),
            _format_number(material.thickness_mm),
        ]
        for material in db.scalars(statement)
    ]


def _format_number(value: float | None) -> str:
    if value is None:
        return ""
    return str(int(value)) if value == int(value) else f"{value:g}"


def _ensure_sheet_exists(service: Any, spreadsheet_id: str, sheet_name: str) -> None:
    try:
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets.properties.title",
        ).execute()
        titles = {sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])}
        if sheet_name in titles:
            return
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()
    except Exception as exc:  # Google client raises HttpError, imported lazily.
        raise GoogleSheetsSyncError(_google_error_message(exc)) from exc


def _quote_sheet_name(sheet_name: str) -> str:
    escaped = sheet_name.replace("'", "''")
    return f"'{escaped}'"


def _google_error_message(exc: Exception) -> str:
    content = getattr(exc, "content", None)
    if isinstance(content, bytes):
        try:
            payload = json.loads(content.decode("utf-8"))
            message = payload.get("error", {}).get("message")
            if message:
                return f"Google Sheets sync failed: {message}"
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return f"Google Sheets sync failed: {exc}"
