"""The sole integration point with the Stocktopus REST API."""

import os
from typing import Any

import httpx
from dotenv import load_dotenv

# Loading here keeps the reusable client functional outside app.main too (for
# maintenance scripts, scheduled jobs, and interactive troubleshooting).
load_dotenv()


class StocktopusError(RuntimeError):
    """A user-friendly error raised for any Stocktopus API failure."""


class StocktopusClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or os.getenv("STOCKTOPUS_API_KEY")
        self.base_url = (base_url or os.getenv("STOCKTOPUS_BASE_URL", "https://stocktop.us/api/v1")).rstrip("/")
        if not self.api_key:
            raise StocktopusError("STOCKTOPUS_API_KEY is missing. Add it to your .env file.")

    async def fetch_stock_page(self, page: int, per_page: int = 100) -> dict[str, Any]:
        """Fetch and validate a single page of stock records."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/stock",
                    headers={"X-API-Key": self.api_key},
                    params={"page": page, "per_page": per_page},
                )
        except httpx.RequestError as exc:
            raise StocktopusError(f"Could not contact Stocktopus: {exc}") from exc

        if response.status_code in (401, 403):
            raise StocktopusError("Stocktopus rejected the API key.")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise StocktopusError(f"Stocktopus returned HTTP {response.status_code}.") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise StocktopusError("Stocktopus returned malformed JSON.") from exc
        if not isinstance(payload, dict) or payload.get("success") is not True:
            message = payload.get("message", "success was false or missing") if isinstance(payload, dict) else "unexpected response"
            raise StocktopusError(f"Stocktopus request failed: {message}.")
        data = payload.get("data")
        # Stocktopus currently uses Laravel pagination, where the record list and
        # pagination fields are nested together under `data`.  Older/deployed
        # variants use the documented top-level data list plus `pagination`.
        # Accept both so this client is not coupled to one server version.
        flat_data = isinstance(data, list)
        nested_data = isinstance(data, dict) and isinstance(data.get("data"), list)
        if not flat_data and not nested_data:
            raise StocktopusError("Stocktopus response did not contain a recognised data list.")
        return payload

    async def fetch_all_stock(self) -> list[dict[str, Any]]:
        """Follow Stocktopus pagination until all stock has been downloaded."""
        records: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = await self.fetch_stock_page(page=page, per_page=100)
            response_data = payload["data"]
            if isinstance(response_data, dict):
                batch = response_data["data"]
                pagination = response_data
            else:
                batch = response_data
                pagination = payload.get("pagination") or {}
            records.extend(item for item in batch if isinstance(item, dict))
            last_page = pagination.get("last_page") or pagination.get("total_pages")
            if (last_page is not None and page >= int(last_page)) or (last_page is None and len(batch) < 100):
                break
            page += 1
        return records
