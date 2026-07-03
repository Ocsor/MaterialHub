"""MaterialHub ASGI application entry point."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .database import Base, engine  # noqa: E402 - environment is loaded first
from .main_paths import STATIC_DIR  # noqa: E402
from .routes import api, materials, sync  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="MaterialHub", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(materials.router)
app.include_router(api.router)
app.include_router(sync.router)


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/materials")
