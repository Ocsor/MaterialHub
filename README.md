# MaterialHub

MaterialHub is a lightweight local material catalogue. Stocktopus remains the stock source of truth; MaterialHub copies Sheet and Roll records into SQLite and adds local mappings without sending changes back to Stocktopus.

## Setup

Python 3.12 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `STOCKTOPUS_API_KEY`. `STOCKTOPUS_BASE_URL` defaults to `https://stocktop.us/api/v1`.

## Run

```powershell
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/materials>. The database and table are created automatically at startup. API documentation is available at <http://127.0.0.1:8000/docs>.

To synchronise, select **Sync from Stocktopus** on the materials page. This calls every `/stock` page with 100 records per page. Sheet and Roll records are inserted or refreshed, missing records are marked inactive, and local fields are never overwritten. New records start with Friendly Name copied from Name; Matex is inferred when the name contains exactly one configured material keyword.

To apply these defaults to blank fields in an existing database without overwriting local edits, run:

```powershell
python -m app.backfill
```

## Database

`materials.db` contains one `materials` table. Stocktopus-owned identity, classification, size, stock, supplier, raw JSON and timestamp columns are refreshed by sync. `friendly_name`, `matex`, `prepit`, `imp`, `notes`, and `sort_order` are editable local fields and are deliberately absent from the sync field mapping.

SQLite creates `materials.db` on first application startup rather than storing a binary database in source control.

## API

- `GET /api/materials` — active materials, ordered by sort order, friendly name, then name
- `GET /api/materials/all` — active and inactive materials
- `GET /api/materials/{id}` — one material by MaterialHub ID

Responses expose the integration-safe subset documented in the OpenAPI page. `display_name` uses a non-blank friendly name and otherwise falls back to the Stocktopus name.

## Architecture

- `app/main.py` configures FastAPI and application startup.
- `app/database.py`, `models.py`, and `schemas.py` own persistence and API shapes.
- `app/stocktopus_client.py` is the only module that communicates with Stocktopus.
- `app/sync.py` contains transactional import/update/deactivation rules.
- `app/routes/` separates the admin interface, public API, and sync endpoint.
- `app/templates/` and `app/static/` provide the framework-free responsive interface.

This separation leaves future aliases, colour profiles, RIP mappings, costing, suppliers, and plugin integrations free to grow into their own models, services, and routers.
