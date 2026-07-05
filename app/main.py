"""MaterialHub ASGI application entry point."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .database import Base, add_missing_material_columns, engine  # noqa: E402 - environment is loaded first
from .main_paths import STATIC_DIR  # noqa: E402
from .routes import api, materials, sync  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    add_missing_material_columns()
    yield


app = FastAPI(title="MaterialHub", version="1.0.0", lifespan=lifespan)
# CEP panels run in an embedded browser and are a different origin from the
# MaterialHub server. The public API is read-only, so allowing LAN clients to
# make cross-origin requests is appropriate here. No credentials are accepted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(materials.router)
app.include_router(api.router)
app.include_router(sync.router)


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/materials")


@app.get("/api/health", tags=["system"])
def health():
    """Lightweight connectivity check for plugins and other clients."""
    return {"status": "ok", "service": "MaterialHub"}
