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
uvicorn app.main:app --reload --port 8765
```

Open <http://127.0.0.1:8765/materials>. The database and table are created automatically at startup. API documentation is available at <http://127.0.0.1:8765/docs>.

To synchronise, select **Sync from Stocktopus** on the materials page. This calls every `/stock` page with 100 records per page. Sheet and Roll records are inserted or refreshed, missing records are marked inactive, and local fields are never overwritten. New records start with Friendly Name copied from Name; Matex is inferred when the name contains exactly one configured material keyword.

To apply these defaults to blank fields in an existing database without overwriting local edits, run:

```powershell
python -m app.backfill
```

## Database

`materials.db` contains one `materials` table. Stocktopus-owned identity, classification, size, stock, supplier, raw JSON and timestamp columns are refreshed by sync. `friendly_name`, `matex`, `prepit`, `imp`, `notes`, and `sort_order` are editable local fields and are deliberately absent from the sync field mapping.

SQLite creates `materials.db` on first application startup rather than storing a binary database in source control.

## Export

The Materials page **Export** button writes files to `MATERIALHUB_EXPORT_PATH` from `.env`, overwriting any existing files with the same names. It creates `prepit_xml.zip`, `imp_materials.csv`, `prepit_rolls.txt`, and `prepit_sheets.txt`. XML templates live in `Resources/Prepit_templates`; Matex-to-registration colour rules are edited in `Resources/prepit_template_rules.json`.

## API

- `GET /api/materials` — active materials, ordered by sort order, friendly name, then name
- `GET /api/materials/all` — active and inactive materials
- `GET /api/materials/{id}` — one material by MaterialHub ID
- `GET /api/materials/lookup?q=clear&kind=material&limit=25` — searchable application lookup
- `GET /api/materials/lookup?q=gloss&kind=laminate&limit=25` — laminate-only lookup
- `GET /api/health` — lightweight client connectivity check

## Access from other computers

Run MaterialHub on its server PC so it listens on the local network:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8765
```

Allow inbound TCP port 8765 on the server's private Windows Firewall profile,
then configure clients with the server's stable hostname or IP, for example
`http://materialhub-pc:8765`. CEP panels can use the lookup endpoints directly;
MaterialHub supplies the cross-origin response headers they require.

Responses expose the integration-safe subset documented in the OpenAPI page. `display_name` uses a non-blank friendly name and otherwise falls back to the Stocktopus name.

## Architecture

- `app/main.py` configures FastAPI and application startup.
- `app/database.py`, `models.py`, and `schemas.py` own persistence and API shapes.
- `app/stocktopus_client.py` is the only module that communicates with Stocktopus.
- `app/sync.py` contains transactional import/update/deactivation rules.
- `app/routes/` separates the admin interface, public API, and sync endpoint.
- `app/templates/` and `app/static/` provide the framework-free responsive interface.

This separation leaves future aliases, colour profiles, RIP mappings, costing, suppliers, and plugin integrations free to grow into their own models, services, and routers.
