import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud, models, schemas, scraper
from app.database import SessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent

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


@app.on_event("startup")
def startup_event():
    global initial_scrape_in_progress
    # Check if the database has any tracks. A new DB will be empty.
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

        # Run scrape in a background thread to not block the server
        scrape_thread = threading.Thread(target=scrape_and_populate_task)
        scrape_thread.start()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
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


@app.post("/scrape")
def scrape_and_populate(background_tasks: BackgroundTasks):
    # Reset status before starting
    with open(SCRAPE_STATUS_FILE, "w") as f:
        f.write("idle")
    background_tasks.add_task(scrape_and_populate_task)
    return {"message": "Scraping has been started in the background."}


@app.get("/api/scrape-status")
def get_scrape_status():
    if os.path.exists(SCRAPE_STATUS_FILE):
        with open(SCRAPE_STATUS_FILE, "r") as f:
            status = f.read().strip()
        return {"status": status}
    return {"status": "idle"}


@app.get("/rated_tracks")
def read_rated_tracks(
    request: Request,
    db: Session = Depends(get_db),
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    exact_rating_filter: Optional[int] = None,
):
    if not sort_by:
        sort_by = "rating"
        sort_dir = "desc"

    tracks = crud.get_tracks(
        db,
        rated_filter="rated",
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        exact_rating_filter=exact_rating_filter,
        rank_filter="all",
    )

    all_db_tracks = crud.get_tracks(db, limit=1000)

    producers_flat = []
    voicebanks_flat = []
    for t in all_db_tracks:
        producers_flat.extend([p.strip() for p in t.producer.split(",")])
        voicebanks_flat.extend([v.strip() for v in t.voicebank.split(",")])

    all_producers = sorted(list(set(producers_flat)))
    all_voicebanks = sorted(list(set(voicebanks_flat)))

    stats = crud.get_rating_statistics(db)

    return templates.TemplateResponse(
        "rated.html",
        {
            "request": request,
            "tracks": tracks,
            "all_producers": all_producers,
            "all_voicebanks": all_voicebanks,
            "stats": stats,
        },
    )


@app.get("/playlists")
def view_playlists_page(request: Request, db: Session = Depends(get_db)):
    playlists = crud.get_playlists(db)
    return templates.TemplateResponse(
        "playlists.html", {"request": request, "playlists": playlists}
    )


@app.get("/playlist/{playlist_id}")
def view_playlist_detail_page(
    playlist_id: int, request: Request, db: Session = Depends(get_db)
):
    db_playlist = crud.get_playlist(db, playlist_id)
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    return templates.TemplateResponse(
        "playlist_view.html", {"request": request, "playlist": db_playlist}
    )


@app.get("/playlist/edit/{playlist_id}")
def edit_playlist_page(
    playlist_id: int, request: Request, db: Session = Depends(get_db)
):
    db_playlist = crud.get_playlist(db, playlist_id)
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Get all tracks to populate the left-hand side
    all_tracks = crud.get_tracks(
        db, limit=10000, sort_by="title"
    )  # Fetch all, sorted by title

    return templates.TemplateResponse(
        "playlist_edit.html",
        {
            "request": request,
            "playlist": db_playlist,
            "all_tracks": all_tracks,
        },
    )


@app.get("/_/rated_tracks_table_body", response_class=JSONResponse)
def get_rated_tracks_table_body(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    limit: str = "all",
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    exact_rating_filter: Optional[int] = None,
):
    if not sort_by:
        sort_by = "rating"
        sort_dir = "desc"
    # 1. Get the total count of tracks matching THIS view's filters
    total_tracks = crud.get_tracks_count(
        db,
        rated_filter="rated",
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        exact_rating_filter=exact_rating_filter,
        rank_filter="all",  # Rated tracks can be on or off the chart
    )

    # 2. Calculate pagination variables
    limit_val = total_tracks
    if limit.isdigit() and int(limit) > 0:
        limit_val = int(limit)

    total_pages = (total_tracks + limit_val - 1) // limit_val if limit_val > 0 else 1
    skip = (page - 1) * limit_val

    # 3. Get the paginated tracks
    tracks = crud.get_tracks(
        db,
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
    )

    # 4. Render the HTML partial
    table_body_html = templates.get_template("partials/tracks_table_body.html").render(
        {"request": request, "tracks": tracks}
    )

    # 5. Return the JSON structure the JavaScript expects
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


@app.get("/_/tracks_table_body")
def get_tracks_table_body(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    limit: str = "all",
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
):
    total_tracks = crud.get_tracks_count(
        db,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        rank_filter=rank_filter,
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
        skip=skip,
        limit=limit_val,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        rank_filter=rank_filter,
    )

    table_body_html = templates.get_template("partials/tracks_table_body.html").render(
        {"request": request, "tracks": tracks}
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


@app.get("/options")
def read_options(request: Request):
    return templates.TemplateResponse("options.html", {"request": request})


@app.get("/api/backup/ratings")
def backup_ratings(db: Session = Depends(get_db)):
    rated_tracks = db.query(models.Track).join(models.Rating).all()
    backup_data = []
    for track in rated_tracks:
        backup_data.append(
            {
                "link": track.link,
                "title": track.title,
                "producer": track.producer,
                "voicebank": track.voicebank,
                "published_date": track.published_date.isoformat(),
                "title_jp": track.title_jp,
                "image_url": track.image_url,
                "rating": track.ratings[0].rating if track.ratings else None,
                "notes": track.ratings[0].notes if track.ratings else None,
            }
        )
    return backup_data


@app.post("/api/restore/ratings")
async def restore_ratings(file: UploadFile = File(...), db: Session = Depends(get_db)):
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
                "image_url": item.get("image_url"),
                "rank": None,  # New tracks from backup are unranked
            }
            track = crud.create_track(db, track_data)
            created_count += 1
        else:
            updated_count += 1

        if item.get("rating") is not None:
            crud.create_rating(db, track.id, item["rating"], item.get("notes"))

    return {"created": created_count, "updated": updated_count}


@app.get("/")
def read_root(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    limit: str = "all",
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
):
    global initial_scrape_in_progress
    if initial_scrape_in_progress:
        if os.path.exists(SCRAPE_STATUS_FILE):
            with open(SCRAPE_STATUS_FILE, "r") as f:
                status = f.read().strip()
                if status in ["completed", "no_changes"]:
                    initial_scrape_in_progress = False

    if initial_scrape_in_progress:
        return templates.TemplateResponse("scraping.html", {"request": request})

    filters = {
        "rated_filter": rated_filter,
        "title_filter": title_filter,
        "producer_filter": producer_filter,
        "voicebank_filter": voicebank_filter,
        "rank_filter": rank_filter,
    }
    total_tracks = crud.get_tracks_count(
        db,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        rank_filter=rank_filter,
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
        skip=skip,
        limit=limit_val,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        rank_filter=rank_filter,
    )

    all_db_tracks = crud.get_tracks(db, limit=1000)

    producers_flat = []
    voicebanks_flat = []
    for t in all_db_tracks:
        producers_flat.extend([p.strip() for p in t.producer.split(",")])
        voicebanks_flat.extend([v.strip() for v in t.voicebank.split(",")])

    all_producers = sorted(list(set(producers_flat)))
    all_voicebanks = sorted(list(set(voicebanks_flat)))

    last_update = crud.get_last_update_time(db)
    update_age_days = None
    is_db_outdated = False
    if last_update:
        # Assuming updated_at is a naive datetime stored in UTC
        update_age = datetime.utcnow() - last_update.updated_at
        update_age_days = update_age.days
        if update_age.total_seconds() > 24 * 3600:
            is_db_outdated = True

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tracks": tracks,
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
        },
    )


@app.post("/rate/{track_id}/delete")
def delete_rating_endpoint(track_id: int, db: Session = Depends(get_db)):
    crud.delete_rating(db, track_id=track_id)
    # Return a 204 No Content response, which is standard for successful actions with no body
    return Response(status_code=204)


@app.post("/rate/{track_id}")
def rate_track(
    track_id: int,
    rating: int = Form(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    crud.create_rating(db, track_id=track_id, rating=rating, notes=notes)
    return Response(status_code=204)


@app.get("/api/vocadb_artist_search")
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


@app.get("/api/vocadb_search")
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


@app.get("/api/vocadb_lyrics/{song_id}")
def get_vocadb_lyrics(song_id: int):
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


@app.get("/api/playlists", response_model=list[schemas.PlaylistSimple])
def get_user_playlists(db: Session = Depends(get_db)):
    """Get a simple list of all playlists (id and name)."""
    return crud.get_playlists(db)


@app.post("/api/playlists", response_model=schemas.PlaylistSimple)
def create_new_playlist(
    playlist: schemas.PlaylistCreate, db: Session = Depends(get_db)
):
    """Create a new, empty playlist."""
    return crud.create_playlist(db, playlist)


@app.post("/api/playlists/{playlist_id}/tracks/{track_id}")
def add_track_to_a_playlist(
    playlist_id: int, track_id: int, db: Session = Depends(get_db)
):
    """Add a single track to a playlist."""
    db_playlist = crud.add_track_to_playlist(
        db, playlist_id=playlist_id, track_id=track_id
    )
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return Response(status_code=200, content="Track added successfully")


@app.delete("/api/playlists/{playlist_id}/tracks/{track_id}")
def remove_track_from_a_playlist(
    playlist_id: int, track_id: int, db: Session = Depends(get_db)
):
    """Remove a single track from a playlist."""
    crud.remove_track_from_playlist(db, playlist_id=playlist_id, track_id=track_id)
    return Response(status_code=200, content="Track removed successfully")


@app.post("/api/playlists/{playlist_id}/reorder")
def reorder_a_playlist(
    playlist_id: int, track_ids: list[int], db: Session = Depends(get_db)
):
    """Update the order of all tracks in a playlist."""
    crud.reorder_playlist(db, playlist_id=playlist_id, track_ids=track_ids)
    return Response(status_code=200, content="Playlist reordered successfully")


@app.put("/api/playlists/{playlist_id}", response_model=schemas.PlaylistSimple)
def update_playlist_details(
    playlist_id: int, playlist_update: PlaylistUpdate, db: Session = Depends(get_db)
):
    """Update a playlist's name and description."""
    db_playlist = crud.update_playlist(
        db,
        playlist_id=playlist_id,
        name=playlist_update.name,
        description=playlist_update.description,
    )
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return db_playlist


@app.get("/api/playlists/export")
def export_all_playlists(db: Session = Depends(get_db)):
    """Exports all playlists and their tracks to a JSON format."""
    return crud.export_playlists(db)


@app.post("/api/playlists/import-single")
async def import_single_playlist(
    file: UploadFile = File(...), db: Session = Depends(get_db)
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
            db, [data]
        )  # We can reuse the main import logic by wrapping it in a list

        status = "created" if created > 0 else "updated"
        return {"status": status, "count": created + updated}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/api/playlists/{playlist_id}/export")
def export_single_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Exports a single playlist and its tracks to a JSON format."""
    playlist = crud.export_single_playlist(db, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return playlist


@app.delete("/api/playlists/{playlist_id}")
def delete_a_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Deletes a playlist and all its track associations."""
    success = crud.delete_playlist(db, playlist_id=playlist_id)
    if not success:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return Response(status_code=200, content="Playlist deleted successfully")
