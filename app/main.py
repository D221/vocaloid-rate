import gettext
import json
import logging
import os
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from gettext import NullTranslations
from pathlib import Path
from typing import AsyncGenerator, Optional
from urllib.parse import quote

import requests
from alembic.config import Config
from babel.support import Translations
from fastapi import (
    BackgroundTasks,
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from alembic import command
from app import crud, models, schemas, scraper
from app.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_optional_current_user,
)
from app.database import SessionLocal
from app.security import ACCESS_TOKEN_EXPIRE_MINUTES

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

# Global variable to store the base path for resources
RESOURCE_BASE_PATH: Optional[Path] = None


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global RESOURCE_BASE_PATH
    # Determine the base path for resources, handling PyInstaller freezing
    if getattr(sys, "frozen", False):
        # Running in a PyInstaller bundle
        RESOURCE_BASE_PATH = Path(sys._MEIPASS)  # type: ignore
    else:
        # Running in a development environment
        RESOURCE_BASE_PATH = Path(__file__).resolve().parent.parent  # Project root

    # Run alembic migrations
    alembic_ini_path = RESOURCE_BASE_PATH / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    command.upgrade(alembic_cfg, "head")

    global initial_scrape_in_progress
    db = SessionLocal()
    track_count = db.query(models.Track).count()
    db.close()

    if track_count == 0:
        logging.info("Database is empty. Starting initial scrape.")
        initial_scrape_in_progress = True
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        with open(SCRAPE_STATUS_FILE, "w") as f:
            f.write("in_progress")
        scrape_thread = threading.Thread(target=initial_scrape_task)
        scrape_thread.start()

    def is_running_in_pyinstaller():
        return getattr(sys, "frozen", False)

    if is_running_in_pyinstaller():
        threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000")).start()

    print("--- Application startup complete. ---")
    yield
    print("--- Application shutting down. ---")


app = FastAPI(lifespan=app_lifespan)


app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    """
    Middleware to add Cache-Control headers for static files.
    """
    response = await call_next(request)
    # Check if the request is for a file in your /static/ directory
    if request.url.path.startswith("/static/"):
        # Cache for 1 day (in seconds). You can adjust this value.
        # 86400 seconds = 24 hours
        response.headers["Cache-Control"] = "public, max-age=86400"
    return response


# models.Base.metadata.create_all(bind=engine) # This is now handled by Alembic

BASE_DIR = Path(__file__).resolve().parent


# --- i18n setup ---
SUPPORTED_LOCALES = ["en", "ja"]
DEFAULT_LOCALE = "en"


async def get_slim_mode(viewModeSlim: Optional[str] = Cookie(None)) -> bool:
    return viewModeSlim == "true"


def get_locale(request: Request) -> str:
    lang_query = request.query_params.get("lang")
    if lang_query and lang_query in SUPPORTED_LOCALES:
        return lang_query

    lang_cookie = request.cookies.get("language")
    if lang_cookie and lang_cookie in SUPPORTED_LOCALES:
        return lang_cookie

    accept_language = request.headers.get("accept-language")
    if accept_language:
        for lang_code in accept_language.split(","):
            lang_code_clean = lang_code.strip().split(";")[0].lower()

            if lang_code_clean in SUPPORTED_LOCALES:
                return lang_code_clean

            base_lang = lang_code_clean.split("-")[0]
            if base_lang in SUPPORTED_LOCALES:
                return base_lang

    return DEFAULT_LOCALE


class TranslationProxy(Translations):
    """
    A proxy for a translation object that ensures the .info() dictionary
    always contains a 'language' key. All other methods are passed through
    to the wrapped translation object.
    """

    def __init__(
        self, inner_translation: Translations | NullTranslations, language: str
    ):
        # We don't call super().__init__() because Translations doesn't have a standard one.
        self._inner = inner_translation
        self._language = language

    def gettext(self, message: str) -> str:
        return self._inner.gettext(message)

    def ngettext(self, msgid1: str, msgid2: str, n: int) -> str:
        return self._inner.ngettext(msgid1, msgid2, n)

    def info(self) -> dict:
        d = {}
        # Ensure we don't crash if the inner .info() method fails
        if hasattr(self._inner, "info"):
            try:
                d.update(self._inner.info())
            except Exception:
                d = {}  # Reset on failure
        d.setdefault("language", self._language)
        return d

    def __getattr__(self, name):
        """Pass through any other attribute/method calls to the inner object."""
        return getattr(self._inner, name)


def get_translations(
    locale: str = Depends(get_locale),
) -> Translations | NullTranslations:
    """
    Load translations and ensure .info() contains a 'language' key so callers
    can safely do translations.info()['language'].
    """
    if RESOURCE_BASE_PATH is None:
        current_base_path = Path(__file__).resolve().parent.parent
        logging.warning(
            "RESOURCE_BASE_PATH was None, re-evaluating for dev environment."
        )
    else:
        current_base_path = RESOURCE_BASE_PATH

    locales_path = current_base_path / "locales"

    try:
        logging.info(
            f"Attempting to load translations from: {locales_path} for locale {locale}"
        )
        t = gettext.translation(
            "messages", localedir=str(locales_path), languages=[locale]
        )
        logging.info(f"gettext.translation successful for locale {locale}.")
        # The TranslationProxy class is now always available.
        return TranslationProxy(t, locale)

    except Exception:
        logging.warning(
            f"Translations not found for {locale} at {locales_path}. Falling back to default."
        )
        # On failure, wrap NullTranslations to uphold the .info()['language'] contract.
        return TranslationProxy(NullTranslations(), locale)


def LocaleTemplateResponse(
    template_name: str,
    context: dict,
    request: Request,
    translations: Translations,
):
    """
    A helper that automatically adds locale to the context
    and sets the language cookie on the response.
    """
    # 1. Automatically add the locale to the context
    context["locale"] = translations.info()["language"]

    # 2. Create the response object
    response = templates.TemplateResponse(template_name, context)

    # 3. Automatically set the language cookie
    response.set_cookie(key="language", value=get_locale(request))
    return response


@app.get("/static/sw.js", tags=["Internal"])
async def serve_sw(request: Request):
    """
    Serves the service worker file with the required Service-Worker-Allowed header.
    """
    sw_path = BASE_DIR / "static" / "sw.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="Service worker not found.")

    with open(sw_path, "r", encoding="utf-8") as f:
        content = f.read()

    return Response(
        content=content,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

DATA_DIR = "data"
SCRAPE_STATUS_FILE = os.path.join(DATA_DIR, "scrape_status.txt")

initial_scrape_in_progress = False


class PlaylistUpdate(BaseModel):
    name: str
    description: Optional[str] = None


class SinglePlaylistImport(BaseModel):
    name: str
    description: Optional[str] = None
    tracks: list[str]  # List of track URLs


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initial_scrape_task():
    db = SessionLocal()
    try:
        logging.info("Initial Scrape: Starting full scrape.")
        final_status = "completed"
        try:
            new_tracks_count = 0
            all_scraped_tracks = []
            for page in range(1, 7):
                with open(SCRAPE_STATUS_FILE, "w") as f:
                    f.write(f"in_progress:{page}/6")
                all_scraped_tracks.extend(scraper._scrape_single_page(page))

            logging.info(
                f"Full scrape finished. Found {len(all_scraped_tracks)} tracks. Adding to database..."
            )

            for track_data in all_scraped_tracks:
                existing_track = crud.get_track_by_link(db, track_data["link"])
                if existing_track:
                    logging.info(
                        f"Track with link {track_data['link']} already exists. Skipping."
                    )
                else:
                    db_track = models.Track(**track_data)
                    db.add(db_track)
                    new_tracks_count += 1

            logging.info(f"Added {new_tracks_count} new tracks.")
            logging.info("Committing all changes to the database...")
            db.commit()
            crud.create_update_log(db)
            logging.info("Database commit successful and update time logged.")

        finally:
            with open(SCRAPE_STATUS_FILE, "w") as f:
                f.write(final_status)
            global initial_scrape_in_progress
            initial_scrape_in_progress = False
    finally:
        db.close()


def scrape_and_populate_task():
    db = SessionLocal()
    try:
        # 1. Scrape only page 1 to check for changes.
        logging.info("Smart Scrape: Checking page 1 for changes...")
        scraped_page_1 = scraper._scrape_single_page(1)
        if not scraped_page_1:
            raise Exception("Failed to scrape page 1.")

        # Change the data structure from a dictionary to a sorted list of tuples.
        # This correctly preserves duplicate ranks.
        scraped_ranks_list = sorted(
            [(track["rank"], track["link"]) for track in scraped_page_1]
        )

        db_top_50 = (
            db.query(models.Track).filter(models.Track.rank.between(1, 50)).all()
        )
        # Create the same structure for the database data.
        db_ranks_list = sorted([(track.rank, track.link) for track in db_top_50])

        # The comparison is now a simple, direct comparison of the two lists.
        # This will correctly handle cases with duplicate ranks.
        if scraped_ranks_list == db_ranks_list:
            logging.info(
                "Smart Scrape: No changes found on page 1. The ranking is already up-to-date."
            )
            with open(SCRAPE_STATUS_FILE, "w") as f:
                f.write("no_changes")
            return

        # If we reach here, it means changes were found.
        logging.info("Smart Scrape: Changes detected! Proceeding with full scrape.")
        with open(SCRAPE_STATUS_FILE, "w") as f:
            f.write("in_progress:1/6")

        final_status = "completed"
        try:
            remaining_pages_tracks = []
            for page in range(2, 7):
                with open(SCRAPE_STATUS_FILE, "w") as f:
                    f.write(f"in_progress:{page}/6")
                remaining_pages_tracks.extend(scraper._scrape_single_page(page))

            all_scraped_tracks = scraped_page_1 + remaining_pages_tracks
            logging.info(
                f"Full scrape finished. Found {len(all_scraped_tracks)} tracks. Processing database..."
            )

            logging.info("Resetting all track ranks to NULL...")
            db.query(models.Track).update({"rank": None})

            scraped_links = [t["link"] for t in all_scraped_tracks]
            existing_tracks_map = {
                track.link: track
                for track in db.query(models.Track)
                .filter(models.Track.link.in_(scraped_links))
                .all()
            }

            new_tracks_count = 0
            updated_tracks_count = 0

            for track_data in all_scraped_tracks:
                link = track_data["link"]
                db_track = existing_tracks_map.get(link)
                if db_track:
                    is_changed = (
                        db_track.rank != track_data["rank"]
                        or db_track.title != track_data["title"]
                    )
                    if is_changed:
                        for key, value in track_data.items():
                            setattr(db_track, key, value)
                        logging.info(
                            f"UPDATED: '{track_data['title']}' (Rank is now {track_data['rank']})"
                        )
                        updated_tracks_count += 1
                else:
                    db_track = models.Track(**track_data)
                    db.add(db_track)
                    logging.info(
                        f"ADDED: '{track_data['title']}' (Rank {track_data['rank']})"
                    )
                    new_tracks_count += 1

            logging.info("--- Scrape Summary ---")
            logging.info(f"New tracks added: {new_tracks_count}")
            logging.info(f"Existing tracks updated: {updated_tracks_count}")

            logging.info("Committing all changes to the database...")
            db.commit()
            crud.create_update_log(db)
            logging.info("Database commit successful and update time logged.")

        except Exception as e:
            final_status = "error"
            logging.error(f"An error occurred in the scrape task: {e}", exc_info=True)
            db.rollback()

        finally:
            with open(SCRAPE_STATUS_FILE, "w") as f:
                f.write(final_status)
    finally:
        db.close()


def time_ago_filter(date: datetime) -> str:
    """Simplified 'time ago' that omits seconds/minutes/hours; uses today, days, months, years."""
    now = datetime.now(timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)

    diff = now - date
    days = diff.days

    if days == 0:
        return "Today"
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


templates.env.filters["time_ago"] = time_ago_filter


@app.post("/scrape", tags=["Scraping"])
def scrape_and_populate(background_tasks: BackgroundTasks):
    # Reset status before starting
    with open(SCRAPE_STATUS_FILE, "w") as f:
        f.write("idle")
    background_tasks.add_task(scrape_and_populate_task)
    return {"message": "Scraping has been started in the background."}


@app.get("/api/scrape-status", tags=["Scraping"])
def get_scrape_status():
    if os.path.exists(SCRAPE_STATUS_FILE):
        with open(SCRAPE_STATUS_FILE, "r") as f:
            status = f.read().strip()
        return {"status": status}
    return {"status": "idle"}


@app.get("/rated_tracks", tags=["Pages"])


def read_rated_tracks(


    request: Request,


    db: Session = Depends(get_db),


    current_user: Optional[models.User] = Depends(get_optional_current_user),


    page: int = 1,


    limit: str = "all",


    title_filter: Optional[str] = None,


    producer_filter: Optional[str] = None,


    voicebank_filter: Optional[str] = None,


    sort_by: Optional[str] = None,


    sort_dir: str = "asc",


    exact_rating_filter: Optional[int] = None,


    translations: Translations = Depends(get_translations),


):


    if current_user is None:


        return RedirectResponse(url="/login")





    locale = translations.info()["language"]


    if not sort_by:


        sort_by = "rating"


        sort_dir = "desc"





    filters = {


        "title_filter": title_filter,


        "producer_filter": producer_filter,


        "voicebank_filter": voicebank_filter,


        "exact_rating_filter": exact_rating_filter,


    }





    total_tracks = crud.get_tracks_count(


        db,


        user_id=current_user.id,


        rated_filter="rated",


        title_filter=title_filter,


        producer_filter=producer_filter,


        voicebank_filter=voicebank_filter,


        exact_rating_filter=exact_rating_filter,


        rank_filter="all",


        locale=locale,


    )





    limit_val = total_tracks if limit == "all" else int(limit)


    total_pages = (total_tracks + limit_val - 1) // limit_val if limit_val > 0 else 1


    skip = (page - 1) * limit_val





    tracks = crud.get_tracks(


        db,


        user_id=current_user.id,


        skip=skip,


        limit=limit_val,


        rated_filter="rated",


        title_filter=title_filter,


        producer_filter=producer_filter,


        voicebank_filter=voicebank_filter,


        sort_by=sort_by,


        sort_dir=sort_dir,


        exact_rating_filter=exact_rating_filter,


        rank_filter="all",


        locale=locale,


    )





    all_db_tracks = crud.get_tracks(db, user_id=current_user.id, limit=1000, rank_filter="all")





    producers_flat = []


    voicebanks_flat = []


    for t in all_db_tracks:


        if locale == "ja" and t.producer_jp:


            producers_flat.extend([p.strip() for p in t.producer_jp.split(",")])


        else:


            producers_flat.extend([p.strip() for p in t.producer.split(",")])





        if locale == "ja" and t.voicebank_jp:


            voicebanks_flat.extend([v.strip() for v in t.voicebank_jp.split(",")])


        else:


            voicebanks_flat.extend([v.strip() for v in t.voicebank.split(",")])





    all_producers = sorted(list(set(producers_flat)))


    all_voicebanks = sorted(list(set(voicebanks_flat)))





    stats = crud.get_rating_statistics(db, user_id=current_user.id, locale=locale)


    tracks_for_json = [track.to_dict() for track in tracks]


    tracks_json_string = json.dumps(tracks_for_json)





    context = {


        "request": request,


        "_": translations.gettext,


        "tracks": tracks,


        "tracks_json": tracks_json_string,


        "all_producers": all_producers,


        "all_voicebanks": all_voicebanks,


        "stats": stats,


        "filters": filters,


        "pagination": {


            "page": page,


            "limit": limit,


            "total_pages": total_pages,


            "total_tracks": total_tracks,


        },


    }





    return LocaleTemplateResponse(


        "rated.html",


        context,


        request=request,


        translations=translations,


    )


@app.get("/playlists", tags=["Pages"])
def view_playlists_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    if current_user is None:
        return RedirectResponse(url="/login")

    playlists = crud.get_playlists(db, user_id=current_user.id)
    context = {"request": request, "_": translations.gettext, "playlists": playlists}

    return LocaleTemplateResponse(
        "playlists.html",
        context,
        request=request,
        translations=translations,
    )


@app.get("/playlist/{playlist_id}", tags=["Pages"])
def view_playlist_detail_page(
    playlist_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    page: int = 1,
    limit: str = "all",
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    translations: Translations = Depends(get_translations),
):
    if current_user is None:
        return RedirectResponse(url="/login")

    locale = translations.info()["language"]
    db_playlist = crud.get_playlist(db, playlist_id)
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Check ownership
    if db_playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this playlist"
        )

    filters = {
        "title_filter": title_filter,
        "producer_filter": producer_filter,
        "voicebank_filter": voicebank_filter,
    }

    # Use our new functions to get the initial filtered/paginated track list
    total_tracks = crud.get_playlist_tracks_count(
        db, playlist_id=playlist_id, locale=locale, **filters
    )
    limit_val = total_tracks if limit == "all" else int(limit)
    total_pages = (total_tracks + limit_val - 1) // limit_val if limit_val > 0 else 1
    skip = (page - 1) * limit_val

    tracks_in_playlist = crud.get_playlist_tracks_filtered(
        db,
        playlist_id=playlist_id,
        skip=skip,
        limit=limit_val,
        sort_by=sort_by,
        sort_dir=sort_dir,
        locale=locale,
        **filters,
    )

    # Get all unique producers/voicebanks *within this playlist* for the datalists
    all_playlist_tracks = [pt.track for pt in db_playlist.playlist_tracks if pt.track]
    producers_flat = []
    voicebanks_flat = []
    for t in all_playlist_tracks:
        if locale == "ja" and t.producer_jp:
            producers_flat.extend([p.strip() for p in t.producer_jp.split(",")])
        else:
            producers_flat.extend([p.strip() for p in t.producer.split(",")])

        if locale == "ja" and t.voicebank_jp:
            voicebanks_flat.extend([v.strip() for v in t.voicebank_jp.split(",")])
        else:
            voicebanks_flat.extend([v.strip() for v in t.voicebank.split(",")])
    all_producers = sorted(list(set(producers_flat)))
    all_voicebanks = sorted(list(set(voicebanks_flat)))

    tracks_for_json = [track.to_dict() for track in tracks_in_playlist]
    tracks_json_string = json.dumps(tracks_for_json)

    context = {
        "request": request,
        "_": translations.gettext,
        "playlist": db_playlist,
        "tracks": tracks_in_playlist,
        "tracks_json": tracks_json_string,
        "all_producers": all_producers,
        "all_voicebanks": all_voicebanks,
        "filters": filters,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_tracks": total_tracks,
        },
    }

    return LocaleTemplateResponse(
        "playlist_view.html",
        context,
        request=request,
        translations=translations,
    )


@app.get("/playlist/edit/{playlist_id}", tags=["Pages"])
def edit_playlist_page(
    playlist_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(
        get_optional_current_user
    ),  # Add current_user
    translations: Translations = Depends(get_translations),
):
    if current_user is None:
        return RedirectResponse(url="/login")

    db_playlist = crud.get_playlist(db, playlist_id)
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Check ownership
    if db_playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to edit this playlist"
        )

    # Get all tracks to populate the left-hand side
    all_tracks = crud.get_tracks(
        db, limit=10000, sort_by="title", rank_filter="all"
    )  # Fetch all, sorted by title

    tracks_for_json = [track.to_dict() for track in all_tracks]
    tracks_json_string = json.dumps(tracks_for_json)

    context = {
        "request": request,
        "_": translations.gettext,
        "playlist": db_playlist,
        "all_tracks": all_tracks,
        "tracks_json": tracks_json_string,
    }

    return LocaleTemplateResponse(
        "playlist_edit.html",
        context,
        request=request,
        translations=translations,
    )


@app.get("/_/get_tracks", response_class=JSONResponse, tags=["Data"])
def get_tracks_partial(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    page: int = 1,
    limit: str = "all",
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
    exact_rating_filter: Optional[int] = None,
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]
    # This logic ensures that if the request is for rated tracks,
    # it correctly includes unranked tracks and sorts by rating by default.
    if rated_filter == "rated":
        rank_filter = "all"
        if not sort_by:
            sort_by = "rating"
            sort_dir = "desc"

    total_tracks = crud.get_tracks_count(
        db,
        user_id=current_user.id,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        rank_filter=rank_filter,
        exact_rating_filter=exact_rating_filter,
        locale=locale,
    )

    limit_val = total_tracks if limit == "all" else int(limit)
    total_pages = (total_tracks + limit_val - 1) // limit_val if limit_val > 0 else 1
    skip = (page - 1) * limit_val

    tracks = crud.get_tracks(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=limit_val,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        rank_filter=rank_filter,
        exact_rating_filter=exact_rating_filter,
        locale=locale,
    )

    tracks_for_json = [track.to_dict() for track in tracks]
    tracks_json_string = json.dumps(tracks_for_json)

    table_body_html = templates.get_template("partials/tracks_table_body.html").render(
        {
            "request": request,
            "_": translations.gettext,
            "tracks": tracks,
            "tracks_json": tracks_json_string,
            "locale": translations.info()["language"],
        }
    )

    return JSONResponse(
        content={
            "table_body_html": table_body_html,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "total_tracks": total_tracks,
            },
        }
    )


@app.get(
    "/api/playlist/{playlist_id}/get_tracks", response_class=JSONResponse, tags=["Data"]
)
def get_playlist_tracks_partial(
    playlist_id: int,
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    limit: str = "all",
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]
    total_tracks = crud.get_playlist_tracks_count(
        db,
        playlist_id=playlist_id,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        locale=locale,
    )

    limit_val = total_tracks if limit == "all" else int(limit)
    total_pages = (total_tracks + limit_val - 1) // limit_val if limit_val > 0 else 1
    skip = (page - 1) * limit_val

    tracks = crud.get_playlist_tracks_filtered(
        db,
        playlist_id=playlist_id,
        skip=skip,
        limit=limit_val,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        locale=locale,
    )

    tracks_for_json = [track.to_dict() for track in tracks]
    tracks_json_string = json.dumps(tracks_for_json)

    table_body_html = templates.get_template("partials/tracks_table_body.html").render(
        {
            "request": request,
            "_": translations.gettext,
            "tracks": tracks,
            "tracks_json": tracks_json_string,
            "locale": translations.info()["language"],
        }
    )

    return JSONResponse(
        content={
            "table_body_html": table_body_html,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "total_tracks": total_tracks,
            },
        }
    )


@app.get(
    "/_/get_recently_added_tracks_partial", response_class=JSONResponse, tags=["Data"]
)
def get_recently_added_tracks_partial(
    request: Request,
    db: Session = Depends(get_db),
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]

    # For recently added, we always want to display all tracks on one "page"
    # so we set the limit to a large number and simplify pagination.
    limit_val = 10000
    page = 1  # Always treat as page 1 since there's no pagination

    tracks = crud.get_recently_added_tracks(
        db,
        skip=0,  # Always skip 0 as we're getting all
        limit=limit_val,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        locale=locale,
    )
    total_tracks = len(tracks)  # Get actual count after filtering

    tracks_for_json = [track.to_dict() for track in tracks]
    tracks_json_string = json.dumps(tracks_for_json)

    table_body_html = templates.get_template("partials/tracks_table_body.html").render(
        {
            "request": request,
            "_": translations.gettext,
            "tracks": tracks,
            "tracks_json": tracks_json_string,
            "locale": translations.info()["language"],
        }
    )

    return JSONResponse(
        content={
            "table_body_html": table_body_html,
            "pagination": {
                "page": page,
                "total_pages": 1,  # Always 1 page
                "total_tracks": total_tracks,
            },
        }
    )


@app.get("/options", tags=["Pages"])
def read_options(
    request: Request, translations: Translations = Depends(get_translations)
):
    context = {"request": request, "_": translations.gettext}

    return LocaleTemplateResponse(
        "options.html",
        context,
        request=request,
        translations=translations,
    )


@app.get("/login", tags=["Pages"])
def login_page(
    request: Request,
    translations: Translations = Depends(get_translations),
):
    context = {"request": request, "_": translations.gettext}
    return LocaleTemplateResponse(
        "login.html",
        context,
        request=request,
        translations=translations,
    )


@app.get("/register", tags=["Pages"])
def register_page(
    request: Request,
    translations: Translations = Depends(get_translations),
):
    context = {"request": request, "_": translations.gettext}
    return LocaleTemplateResponse(
        "register.html",
        context,
        request=request,
        translations=translations,
    )


@app.get("/api/backup/ratings", tags=["Backup & Restore"])
def backup_ratings(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    # Query only tracks rated by the current user
    results = db.query(models.Track, models.Rating).join(models.Rating).filter(models.Rating.user_id == current_user.id).all()
    backup_data = []
    for track, rating_obj in results:
        backup_data.append(
            {
                "link": track.link,
                "title": track.title,
                "producer": track.producer,
                "voicebank": track.voicebank,
                "published_date": track.published_date.isoformat(),
                "title_jp": track.title_jp,
                "producer_jp": track.producer_jp,
                "voicebank_jp": track.voicebank_jp,
                "image_url": track.image_url,
                "rating": rating_obj.rating,
                "notes": rating_obj.notes,
            }
        )
    return backup_data


@app.post("/api/restore/ratings", tags=["Backup & Restore"])
async def restore_ratings(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    filename = getattr(file, "filename", "") or ""
    if not filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Please upload a .json file."
        )

    contents = await file.read()
    try:
        backup_data = json.loads(contents)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file.")

    created_count = 0
    updated_count = 0

    for item in backup_data:
        track = crud.get_track_by_link(db, item["link"])
        if not track:
            track_data = {
                "link": item["link"],
                "title": item["title"],
                "producer": item["producer"],
                "voicebank": item["voicebank"],
                "published_date": datetime.fromisoformat(item["published_date"]),
                "title_jp": item.get("title_jp"),
                "producer_jp": item.get("producer_jp"),
                "voicebank_jp": item.get("voicebank_jp"),
                "image_url": item.get("image_url"),
                "rank": None,  # New tracks from backup are unranked
            }
            track = crud.create_track(db, track_data)
            created_count += 1
        else:
            updated_count += 1

        if item.get("rating") is not None:
            crud.create_rating(
                db,
                track.id,
                user_id=current_user.id,
                rating=item["rating"],
                notes=item.get("notes"),
            )

    return {"created": created_count, "updated": updated_count}


@app.get("/", tags=["Pages"])
def read_root(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    page: int = 1,
    limit: str = "all",
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
    translations: Translations = Depends(get_translations),
    is_slim_mode: bool = Depends(get_slim_mode),
):
    if current_user is None:
        return RedirectResponse(url="/login")

    locale = translations.info()["language"]
    global initial_scrape_in_progress

    if initial_scrape_in_progress:
        return LocaleTemplateResponse(
            "scraping.html",
            {"request": request, "_": translations.gettext},
            request=request,
            translations=translations,
        )

    filters = {
        "rated_filter": rated_filter,
        "title_filter": title_filter,
        "producer_filter": producer_filter,
        "voicebank_filter": voicebank_filter,
        "rank_filter": rank_filter,
    }
    total_tracks = crud.get_tracks_count(
        db,
        user_id=current_user.id,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        rank_filter=rank_filter,
        locale=locale,
    )

    limit_val = 10000  # A large number for "all"
    if limit.isdigit():
        limit_val = int(limit)

    total_pages = 1
    if limit_val != 10000:
        total_pages = (total_tracks + limit_val - 1) // limit_val

    skip = (page - 1) * limit_val if limit_val != 10000 else 0

    tracks = crud.get_tracks(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=limit_val,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        rank_filter=rank_filter,
        locale=locale,
    )

    # 1. Create a list of dictionaries by CALLING the to_dict() method
    tracks_for_json = [track.to_dict() for track in tracks]

    # 2. Convert this list to a JSON string
    tracks_json_string = json.dumps(tracks_for_json)

    all_db_tracks = crud.get_tracks(db, user_id=current_user.id, limit=1000)

    producers_flat = []
    voicebanks_flat = []
    for t in all_db_tracks:
        if locale == "ja" and t.producer_jp:
            producers_flat.extend([p.strip() for p in t.producer_jp.split(",")])
        else:
            producers_flat.extend([p.strip() for p in t.producer.split(",")])

        if locale == "ja" and t.voicebank_jp:
            voicebanks_flat.extend([v.strip() for v in t.voicebank_jp.split(",")])
        else:
            voicebanks_flat.extend([v.strip() for v in t.voicebank.split(",")])

    all_producers = sorted(list(set(producers_flat)))
    all_voicebanks = sorted(list(set(voicebanks_flat)))

    last_update = crud.get_last_update_time(db)
    update_age_days = None
    is_db_outdated = False
    if last_update:
        # Ensure last_update.updated_at is timezone-aware
        if last_update.updated_at.tzinfo is None:
            # Assume it's UTC if naive, as per previous comment/intent
            last_update.updated_at = last_update.updated_at.replace(tzinfo=timezone.utc)

        update_age = datetime.now(timezone.utc) - last_update.updated_at
        update_age_days = update_age.days
        if update_age.total_seconds() > 24 * 3600:
            is_db_outdated = True

    context = {
        "request": request,
        "_": translations.gettext,
        "is_slim_mode": is_slim_mode,
        "tracks": tracks,
        "tracks_json": tracks_json_string,
        "all_producers": all_producers,
        "all_voicebanks": all_voicebanks,
        "last_update": last_update,
        "is_db_outdated": is_db_outdated,
        "update_age_days": update_age_days,
        "filters": filters,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_tracks": total_tracks,
        },
    }

    return LocaleTemplateResponse(
        "index.html",
        context,
        request=request,
        translations=translations,
    )


@app.get("/recently_added", tags=["Pages"])
def read_recently_added(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    translations: Translations = Depends(get_translations),
):
    if current_user is None:
        return RedirectResponse(url="/login")

    locale = translations.info()["language"]

    filters = {
        "title_filter": title_filter,
        "producer_filter": producer_filter,
        "voicebank_filter": voicebank_filter,
    }

    # For recently added, we always want to display all tracks on one "page"
    # so we set the limit to a large number and simplify pagination.
    limit_val = 10000
    page = 1  # Always treat as page 1 since there's no pagination

    tracks = crud.get_recently_added_tracks(
        db,
        skip=0,  # Always skip 0 as we're getting all
        limit=limit_val,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        locale=locale,
    )
    total_tracks = len(tracks)  # Get actual count after filtering

    tracks_for_json = [track.to_dict() for track in tracks]
    tracks_json_string = json.dumps(tracks_for_json)

    all_db_tracks = crud.get_tracks(db, user_id=current_user.id, limit=1000)  # For filter dropdowns

    producers_flat = []
    voicebanks_flat = []
    for t in all_db_tracks:
        if locale == "ja" and t.producer_jp:
            producers_flat.extend([p.strip() for p in t.producer_jp.split(",")])
        else:
            producers_flat.extend([p.strip() for p in t.producer.split(",")])

        if locale == "ja" and t.voicebank_jp:
            voicebanks_flat.extend([v.strip() for v in t.voicebank_jp.split(",")])
        else:
            voicebanks_flat.extend([v.strip() for v in t.voicebank.split(",")])

    all_producers = sorted(list(set(producers_flat)))
    all_voicebanks = sorted(list(set(voicebanks_flat)))

    context = {
        "request": request,
        "_": translations.gettext,
        "tracks": tracks,
        "tracks_json": tracks_json_string,
        "all_producers": all_producers,
        "all_voicebanks": all_voicebanks,
        "filters": filters,
        "pagination": {
            "page": page,
            "total_pages": 1,
            "total_tracks": total_tracks,
        },
        "is_recently_added_page": True,
    }

    # --- REPLACED THIS ---
    return LocaleTemplateResponse(
        "recently_added.html",
        context,
        request=request,
        translations=translations,
    )


@app.get("/api/translations", tags=["Internal"])
def get_js_translations(locale: str = Depends(get_locale)):
    if RESOURCE_BASE_PATH is None:
        raise HTTPException(status_code=500, detail="Resource path not configured.")

    js_translations_path = RESOURCE_BASE_PATH / "locales" / "js_translations.json"
    with open(js_translations_path, "r", encoding="utf-8") as f:
        all_translations = json.load(f)
    return all_translations.get(locale, all_translations["en"])


@app.get("/recommendations", tags=["Pages"])
def read_recommendations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(
        get_optional_current_user
    ),  # Protect endpoint
    translations: Translations = Depends(get_translations),
):
    if current_user is None:
        return RedirectResponse(url="/login")

    stats = crud.get_rating_statistics(
        db, user_id=current_user.id, locale=translations.info()["language"]
    )
    recommended_tracks = crud.get_recommended_tracks(
        db, user_id=current_user.id, locale=translations.info()["language"]
    )
    tracks_for_json = [track.to_dict() for track in recommended_tracks]
    tracks_json_string = json.dumps(tracks_for_json)

    context = {
        "request": request,
        "_": translations.gettext,
        "stats": stats,
        "recommended_tracks": recommended_tracks,
        "tracks_json": tracks_json_string,
    }

    return LocaleTemplateResponse(
        "recommendations.html",
        context,
        request=request,
        translations=translations,
    )


@app.post("/rate/{track_id}/delete", tags=["Ratings"])
def delete_rating_endpoint(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    crud.delete_rating(db, track_id=track_id, user_id=current_user.id)
    # Return a 204 No Content response, which is standard for successful actions with no body
    return Response(status_code=204)


@app.post("/rate/{track_id}", tags=["Ratings"])
def rate_track(
    track_id: int,
    rating: int = Form(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    crud.create_rating(
        db, track_id=track_id, user_id=current_user.id, rating=rating, notes=notes
    )
    return Response(status_code=204)


@app.get("/api/vocadb_artist_search", tags=["VocaDB"])
def search_vocadb_artist(producer: str):
    headers = {"Accept": "application/json"}
    try:
        artist_search_url = f"https://vocadb.net/api/artists?query={quote(producer)}&maxResults=1&sort=FollowerCount"
        artist_response = requests.get(artist_search_url, headers=headers, timeout=10)
        artist_response.raise_for_status()
        artist_data = artist_response.json()

        if artist_data.get("items"):
            artist = artist_data["items"][0]
            artist_id = artist["id"]
            # Artist URLs on VocaDB use the /Ar/ prefix
            artist_url = f"https://vocadb.net/Ar/{artist_id}"
            return {"url": artist_url}
        else:
            return {"url": None}

    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling VocaDB Artist API: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Could not connect to VocaDB API.")
    except Exception as e:
        logging.error(
            f"An unexpected error occurred during VocaDB artist search: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An internal error occurred.")


@app.get("/api/vocadb_search", tags=["VocaDB"])
def search_vocadb(producer: str, title_en: str, title_jp: str | None = None):
    headers = {"Accept": "application/json"}
    try:
        # Step 1: Find the Artist ID (this is the same)
        artist_search_url = f"https://vocadb.net/api/artists?query={quote(producer)}&maxResults=1&sort=FollowerCount"
        artist_response = requests.get(artist_search_url, headers=headers, timeout=10)
        artist_response.raise_for_status()
        artist_data = artist_response.json()

        if not artist_data.get("items"):
            return {"url": None, "song_id": None}
        artist_id = artist_data["items"][0]["id"]

        # Step 2: Search with English title first
        song_search_url = f"https://vocadb.net/api/songs?query={quote(title_en)}&songTypes=Original&artistId[]={artist_id}&maxResults=1&sort=RatingScore"
        song_response = requests.get(song_search_url, headers=headers, timeout=10)
        song_response.raise_for_status()
        song_data = song_response.json()

        # If English search fails AND we have a Japanese title, try it as a fallback
        if not song_data.get("items") and title_jp:
            logging.info(
                f"VocaDB: English search failed for '{title_en}'. Trying Japanese title '{title_jp}'."
            )
            song_search_url = f"https://vocadb.net/api/songs?query={quote(title_jp)}&songTypes=Original&artistId[]={artist_id}&maxResults=1&sort=RatingScore"
            song_response = requests.get(song_search_url, headers=headers, timeout=10)
            song_response.raise_for_status()
            song_data = song_response.json()

        if song_data.get("items"):
            song = song_data["items"][0]
            song_id = song["id"]
            song_url = f"https://vocadb.net/S/{song_id}"
            return {"url": song_url, "song_id": song_id}
        else:
            return {"url": None, "song_id": None}

    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling VocaDB API: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Could not connect to VocaDB API.")
    except Exception as e:
        logging.error(
            f"An unexpected error occurred during VocaDB search: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An internal error occurred.")


@app.get("/api/vocadb_lyrics/{song_id}", tags=["VocaDB"])
def get_vocadb_lyrics(song_id: int, locale: str = Depends(get_locale)):
    headers = {"Accept": "application/json"}
    try:
        api_url = f"https://vocadb.net/api/songs/{song_id}?fields=Lyrics"
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        lyrics_list = data.get("lyrics", [])
        if not lyrics_list:
            return {"lyrics": []}

        available_lyrics = []
        for lyric_data in lyrics_list:
            text = lyric_data.get("value", "").replace("\n", "<br>")
            lang = lyric_data.get("cultureCodes", [""])[0]
            trans_type = lyric_data.get("translationType", "Unknown")
            label = f"{lang.upper()} - {trans_type}"

            if trans_type == "Romanized":
                label = "Romaji"
            elif trans_type == "Translation" and "en" in lang:
                label = "English (Translation)"
            elif trans_type == "Original" and "ja" in lang:
                label = "Japanese (Original)"

            available_lyrics.append(
                {
                    "label": label,
                    "text": text,
                    "source": lyric_data.get("source", ""),
                    "url": lyric_data.get("url", ""),
                    "translation_type": trans_type,
                }
            )

        def sort_key(lyric):
            # New logic based on locale
            if locale == "ja":
                if "Japanese" in lyric["label"]:
                    return 0
                if "Romaji" in lyric["label"]:
                    return 1
                if "English" in lyric["label"]:
                    return 2
            else:  # Default to English first
                if "English" in lyric["label"]:
                    return 0
                if "Romaji" in lyric["label"]:
                    return 1
                if "Japanese" in lyric["label"]:
                    return 2
            return 3

        available_lyrics.sort(key=sort_key)

        return {"lyrics": available_lyrics}

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching lyrics from VocaDB API: {e}", exc_info=True)
        raise HTTPException(
            status_code=503, detail="Could not fetch lyrics from VocaDB."
        )
    except Exception as e:
        logging.error(
            f"An unexpected error occurred during lyrics fetch: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An internal error occurred.")


@app.get(
    "/api/playlists", response_model=list[schemas.PlaylistSimple], tags=["Playlists"]
)
def get_user_playlists(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """Get a simple list of all playlists (id and name) for the current user."""
    return crud.get_playlists(db, user_id=current_user.id)


@app.post("/api/playlists", response_model=schemas.PlaylistSimple, tags=["Playlists"])
def create_new_playlist(
    playlist: schemas.PlaylistCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a new, empty playlist."""
    return crud.create_playlist(db, user_id=current_user.id, playlist=playlist)


@app.post("/api/playlists/{playlist_id}/tracks/{track_id}", tags=["Playlists"])
def add_track_to_a_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Add a single track to a playlist."""
    db_playlist = crud.add_track_to_playlist(
        db, playlist_id=playlist_id, track_id=track_id, user_id=current_user.id
    )
    if not db_playlist:
        raise HTTPException(
            status_code=404, detail="Playlist not found or not owned by user"
        )
    return Response(status_code=200, content="Track added successfully")


@app.delete("/api/playlists/{playlist_id}/tracks/{track_id}", tags=["Playlists"])
def remove_track_from_a_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Remove a single track from a playlist."""
    crud.remove_track_from_playlist(
        db, playlist_id=playlist_id, track_id=track_id, user_id=current_user.id
    )
    return Response(status_code=200, content="Track removed successfully")


@app.post("/api/playlists/{playlist_id}/reorder", tags=["Playlists"])
def reorder_a_playlist(
    playlist_id: int,
    track_ids: list[int],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update the order of all tracks in a playlist."""
    crud.reorder_playlist(
        db, playlist_id=playlist_id, track_ids=track_ids, user_id=current_user.id
    )
    return Response(status_code=200, content="Playlist reordered successfully")


@app.put(
    "/api/playlists/{playlist_id}",
    response_model=schemas.PlaylistSimple,
    tags=["Playlists"],
)
def update_playlist_details(
    playlist_id: int,
    playlist_update: PlaylistUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update a playlist's name and description."""
    db_playlist = crud.update_playlist(
        db,
        playlist_id=playlist_id,
        user_id=current_user.id,  # Pass user_id
        name=playlist_update.name,
        description=playlist_update.description,
    )
    if not db_playlist:
        raise HTTPException(
            status_code=404, detail="Playlist not found or not owned by user"
        )  # Update message
    return db_playlist


@app.get("/api/playlists/export", tags=["Backup & Restore"])
def export_all_playlists(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """Exports all playlists and their tracks to a JSON format."""
    return crud.export_playlists(db, user_id=current_user.id)


@app.post("/api/playlists/import-single", tags=["Backup & Restore"])
async def import_single_playlist(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Imports a single playlist from a JSON file."""
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be .json")

    contents = await file.read()
    try:
        data = json.loads(contents)
        # Validate that it's a single playlist object, not a list
        if not isinstance(data, dict) or "name" not in data or "tracks" not in data:
            raise HTTPException(
                status_code=400, detail="JSON is not a valid single playlist export."
            )

        created, updated = crud.import_playlists(
            db, user_id=current_user.id, data=[data]
        )  # We can reuse the main import logic by wrapping it in a list

        status = "created" if created > 0 else "updated"
        return {"status": status, "count": created + updated}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/api/playlists/{playlist_id}/export", tags=["Backup & Restore"])
def export_single_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Exports a single playlist and its tracks to a JSON format."""
    playlist = crud.export_single_playlist(db, playlist_id, user_id=current_user.id)
    if not playlist:
        raise HTTPException(
            status_code=404, detail="Playlist not found or not owned by user"
        )
    return playlist


@app.delete("/api/playlists/{playlist_id}", tags=["Playlists"])
def delete_a_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Deletes a playlist and all its track associations."""
    success = crud.delete_playlist(db, playlist_id=playlist_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Playlist not found or not owned by user"
        )
    return Response(status_code=200, content="Playlist deleted successfully")


@app.get("/api/tracks/{track_id}/playlist-status", tags=["Data"])
def get_track_playlist_status(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    For a given track, returns two lists of playlists:
    'member_of': playlists the track is already in.
    'not_member_of': playlists the track is not in.
    """
    return crud.get_track_playlist_membership(
        db, track_id=track_id, user_id=current_user.id
    )


@app.get("/api/playlist-snapshot", response_class=JSONResponse, tags=["Data"])
def get_playlist_snapshot_endpoint(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    limit: str = "all",
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
    exact_rating_filter: Optional[int] = None,
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]
    """
    Provides a complete, ordered list of all track IDs that match the current
    filters, along with the page number each track belongs on.
    by the frontend player for continuous playback across pages.
    """
    # This route now supports all filters from both the main page and rated tracks page
    if rated_filter == "rated":
        rank_filter = "all"
        if not sort_by:
            sort_by = "rating"
            sort_dir = "desc"

    return crud.get_playlist_snapshot(
        db=db,
        user_id=current_user.id,
        limit=limit,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        rank_filter=rank_filter,
        exact_rating_filter=exact_rating_filter,
        locale=locale,
    )


@app.get(
    "/api/playlist/{playlist_id}/playlist-snapshot",
    response_class=JSONResponse,
    tags=["Data"],
)
def get_playlist_snapshot_for_playlist_endpoint(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),  # Add current_user
    limit: str = "all",
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]
    """
    Provides a complete, ordered list of all track IDs for a SPECIFIC PLAYLIST
    that match the current filters.
    """
    return crud.get_playlist_snapshot_for_playlist(
        db=db,
        playlist_id=playlist_id,
        user_id=current_user.id,  # Pass user_id
        limit=limit,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        locale=locale,
    )


@app.get("/api/recently-added-snapshot", response_class=JSONResponse, tags=["Data"])
def get_recently_added_snapshot_endpoint(
    db: Session = Depends(get_db),
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]
    """
    Provides a complete, ordered list of all track IDs for recently added tracks
    that match the current filters, along with the page number each track belongs on.
    """
    return crud.get_recently_added_snapshot(
        db=db,
        limit="10000",  # Always fetch all for snapshot
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        locale=locale,
    )


@app.post("/token", response_model=schemas.Token, tags=["Authentication"])
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    logging.info(f"Login attempt for username: {form_data.username}")
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        logging.warning(
            f"Login failed: Incorrect username or password for {form_data.username}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logging.info(f"Login successful for user: {user.email}")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=True,
    )  # Set as httponly cookie
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/users/", response_model=schemas.User, tags=["Authentication"])
def create_user(
    response: Response, user: schemas.UserCreate, db: Session = Depends(get_db)
):
    logging.info(f"Registration attempt for email: {user.email}")
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        logging.warning(f"Registration failed: Email {user.email} already exists")
        raise HTTPException(status_code=400, detail="Email already registered")
    try:
        new_user = crud.create_user(db=db, user=user)
        logging.info(
            f"Successfully created user: {new_user.email} with ID: {new_user.id}"
        )

        # Auto-login: Create and set token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": new_user.email}, expires_delta=access_token_expires
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            secure=True,
        )

        return new_user
    except Exception as e:
        logging.error(f"Database error during user creation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during registration"
        )


@app.get("/users/me/", tags=["Authentication"])
async def read_users_me(
    request: Request,
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    context = {
        "request": request,
        "_": translations.gettext,
        "current_user": current_user,
    }
    return templates.TemplateResponse("partials/user_status.html", context)


@app.post("/logout", tags=["Authentication"])
async def logout(response: Response):
    response.delete_cookie(key="access_token", samesite="lax", secure=True)
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
