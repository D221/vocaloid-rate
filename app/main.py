import logging
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app import crud, models
from app.auth import authenticate_user, get_current_user, get_optional_current_user
from app.constants import BASE_DIR, STATIC_DIR, set_resource_base_path
from app.config import (
    is_local_auth_mode,
    should_run_migrations_on_startup,
    should_use_secure_cookies,
)
from app.database import SessionLocal
from app.dependencies import get_db, templates
from app.routers import auth, pages, playlists, scraping, tracks, vocadb
from app.services.scraping import (
    initial_scrape_task,
    set_initial_scrape_in_progress,
    write_scrape_status,
)
from app.utils.view_helpers import time_ago_filter

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

__all__ = [
    "app",
    "authenticate_user",
    "crud",
    "get_current_user",
    "get_db",
    "get_optional_current_user",
    "is_local_auth_mode",
    "should_use_secure_cookies",
]


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if getattr(sys, "frozen", False):
        resource_base_path = Path(str(getattr(sys, "_MEIPASS")))
    else:
        resource_base_path = Path(__file__).resolve().parent.parent
    set_resource_base_path(resource_base_path)

    if should_run_migrations_on_startup():
        alembic_ini_path = resource_base_path / "alembic.ini"
        alembic_cfg = Config(str(alembic_ini_path))
        command.upgrade(alembic_cfg, "head")
    else:
        logging.info("Skipping Alembic migrations on startup.")

    db = SessionLocal()
    try:
        track_count = db.query(models.Track).count()
    finally:
        db.close()

    if track_count == 0:
        logging.info("Database is empty. Starting initial scrape.")
        set_initial_scrape_in_progress(True)
        write_scrape_status("in_progress")
        scrape_thread = threading.Thread(target=initial_scrape_task)
        scrape_thread.start()

    if getattr(sys, "frozen", False):
        threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000")).start()

    print("--- Application startup complete. ---")
    yield
    print("--- Application shutting down. ---")


app = FastAPI(lifespan=app_lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.get("/static/sw.js", tags=["Internal"])
async def serve_sw(request: Request):
    sw_path = BASE_DIR / "static" / "sw.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="Service worker not found.")

    with open(sw_path, "r", encoding="utf-8") as file_handle:
        content = file_handle.read()

    return Response(
        content=content,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates.env.filters["time_ago"] = time_ago_filter

app.include_router(auth.router)
app.include_router(scraping.router)
app.include_router(vocadb.router)
app.include_router(playlists.router)
app.include_router(tracks.router)
app.include_router(pages.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
