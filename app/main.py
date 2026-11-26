import logging
import sys
import threading
import webbrowser
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from alembic import command
from app import crud, models
from app.auth import authenticate_user, get_current_user, get_optional_current_user
from app.config import (
    is_local_auth_mode,
    should_run_migrations_on_startup,
    should_use_secure_cookies,
)
from app.constants import (
    BASE_DIR,
    STATIC_DIR,
    VALID_PAGE_LIMITS,
    set_resource_base_path,
)
from app.database import SessionLocal
from app.dependencies import get_db, templates
from app.routers import auth, pages, playlists, scraping, sitemap, tracks, vocadb
from app.services.scraping import (
    initial_scrape_task,
    set_initial_scrape_in_progress,
    write_scrape_status,
)
from app.utils.view_helpers import time_ago_filter

logger = logging.getLogger(__name__)


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

# Reject page numbers beyond this as absurd (no legitimate view goes this deep).
_MAX_PAGE = 100_000


@asynccontextmanager
async def app_lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    if getattr(sys, "frozen", False):
        # _MEIPASS is injected at runtime by PyInstaller, so it is not a real
        # attribute on sys and getattr keeps type checkers happy.
        resource_base_path = Path(str(getattr(sys, "_MEIPASS")))  # noqa: B009
    else:
        resource_base_path = Path(__file__).resolve().parent.parent
    set_resource_base_path(resource_base_path)

    if should_run_migrations_on_startup():
        alembic_ini_path = resource_base_path / "alembic.ini"
        alembic_cfg = Config(str(alembic_ini_path))
        command.upgrade(alembic_cfg, "head")
    else:
        logger.info("Skipping Alembic migrations on startup.")

    db = SessionLocal()
    try:
        track_count = db.query(models.Track).count()
    finally:
        db.close()

    if track_count == 0:
        logger.info("Database is empty. Starting initial scrape.")
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

# Paths whose anonymous responses are safe to cache at the edge. Authenticated
# or otherwise personalised responses are forced to private/no-store below.
_PUBLIC_CACHE_EXACT = frozenset(
    {
        "/",
        "/robots.txt",
        "/sitemap.xml",
        "/recently_added",
        "/api/playlist-snapshot",
        "/api/recently-added-snapshot",
    }
)
_PUBLIC_CACHE_PREFIXES = ("/producer/", "/voicebank/", "/_/get_tracks")
# Anonymous edge-cached responses: revalidate in the background and serve stale
# while revalidating so crawlers and repeat visitors rarely invoke the function.
_PUBLIC_CACHE_CONTROL = "public, max-age=0, s-maxage=60, stale-while-revalidate=300"


def _is_public_cacheable_path(path: str) -> bool:
    return path in _PUBLIC_CACHE_EXACT or path.startswith(_PUBLIC_CACHE_PREFIXES)


def _add_vary_cookie(response: Response) -> None:
    existing = response.headers.get("vary")
    if not existing:
        response.headers["Vary"] = "Cookie"
    elif "cookie" not in existing.lower():
        response.headers["Vary"] = f"{existing}, Cookie"


@app.middleware("http")
async def guard_heavy_queries(request: Request, call_next) -> Response:
    """Reject absurd pagination params early with 400 so crawlers cannot force
    pathological queries (e.g. limit=notanumber, page=99999999)."""
    if request.method in ("GET", "HEAD"):
        limit = request.query_params.get("limit")
        if limit is not None and limit not in VALID_PAGE_LIMITS and not limit.isdigit():
            return JSONResponse({"detail": "Invalid limit."}, status_code=400)
        page = request.query_params.get("page")
        if page is not None:
            try:
                if not page.isdigit() or int(page) > _MAX_PAGE:
                    raise ValueError
            except ValueError:
                return JSONResponse({"detail": "Invalid page."}, status_code=400)
    return await call_next(request)


@app.middleware("http")
async def add_cache_control_header(request: Request, call_next) -> Response:
    response = await call_next(request)
    path = request.url.path

    if path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    # Respect an explicit cache-control set by a route (e.g. sitemap).
    if "cache-control" in response.headers:
        return response

    if request.method not in ("GET", "HEAD"):
        return response

    if not _is_public_cacheable_path(path):
        return response

    personalised = "set-cookie" in response.headers or "access_token" in request.cookies
    if personalised:
        # Never let shared caches store user- or session-specific responses.
        response.headers["Cache-Control"] = "private, no-store"
        return response

    _add_vary_cookie(response)
    response.headers["Cache-Control"] = _PUBLIC_CACHE_CONTROL
    return response


@app.get("/static/sw.js", tags=["Internal"])
async def serve_sw(_request: Request) -> Response:
    sw_path = BASE_DIR / "static" / "sw.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="Service worker not found.")

    return Response(
        content=sw_path.read_text(encoding="utf-8"),
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
app.include_router(sitemap.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
