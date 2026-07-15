"""MaterialHub ASGI application entry point."""

from contextlib import asynccontextmanager
import os
from secrets import token_urlsafe

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .database import Base, add_missing_material_columns, engine  # noqa: E402 - environment is loaded first
from .main_paths import STATIC_DIR  # noqa: E402
from .routes import api, auth, materials, sync  # noqa: E402
from .session import SignedCookieSessionMiddleware  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    add_missing_material_columns()
    yield


app = FastAPI(title="MaterialHub", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    SignedCookieSessionMiddleware,
    secret_key=os.getenv("MATERIALHUB_SECRET_KEY") or token_urlsafe(32),
    same_site="lax",
    https_only=os.getenv("MATERIALHUB_COOKIE_HTTPS", "").lower() in {"1", "true", "yes"},
)
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
app.include_router(auth.router)
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
