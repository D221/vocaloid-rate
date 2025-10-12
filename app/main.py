import logging
import os
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Form, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import crud, models, scraper
from .database import SessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

SCRAPE_STATUS_FILE = "scrape_status.txt"


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
        with open(SCRAPE_STATUS_FILE, "w") as f:
            f.write("in_progress")

        final_status = "completed"
        try:
            logging.info("Starting scrape...")
            tracks_from_scraper = scraper.scrape_tracks()
            logging.info(
                f"Scraping finished. Found {len(tracks_from_scraper)} tracks. Processing database..."
            )

            logging.info(
                "Resetting all track ranks to NULL before applying new ranks..."
            )
            db.query(models.Track).update({"rank": None})

            # Fetch existing tracks from the DB that are in the new scrape list
            scraped_links = [t["link"] for t in tracks_from_scraper]
            existing_tracks_map = {
                track.link: track
                for track in db.query(models.Track)
                .filter(models.Track.link.in_(scraped_links))
                .all()
            }

            new_tracks_count = 0
            updated_tracks_count = 0

            for track_data in tracks_from_scraper:
                link = track_data["link"]

                # Check if the track is already in our database
                db_track = existing_tracks_map.get(link)

                if db_track:
                    is_changed = False
                    # Now, a change in rank is guaranteed for any existing track
                    if (
                        db_track.rank != track_data["rank"]
                        or db_track.title != track_data["title"]
                    ):
                        is_changed = True

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
            logging.info("Database commit successful.")

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
    )

    all_db_tracks = crud.get_tracks(db, limit=1000)

    producers_flat = []
    voicebanks_flat = []
    for t in all_db_tracks:
        producers_flat.extend([p.strip() for p in t.producer.split(",")])
        voicebanks_flat.extend([v.strip() for v in t.voicebank.split(",")])

    all_producers = sorted(list(set(producers_flat)))
    all_voicebanks = sorted(list(set(voicebanks_flat)))

    all_producers = sorted(
        list(set(t.producer for t in crud.get_tracks(db, limit=1000)))
    )
    all_voicebanks = sorted(
        list(set(t.voicebank for t in crud.get_tracks(db, limit=1000)))
    )

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


@app.get("/_/rated_tracks_table_body")
def get_rated_tracks_table_body(
    request: Request,
    db: Session = Depends(get_db),
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
):
    # Same logic, just for the partial
    tracks = crud.get_tracks(
        db,
        rated_filter="rated",
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return templates.TemplateResponse(
        "partials/tracks_table_body.html", {"request": request, "tracks": tracks}
    )


@app.get("/_/tracks_table_body")
def get_tracks_table_body(
    request: Request,
    db: Session = Depends(get_db),
    rated_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
):
    tracks = crud.get_tracks(
        db,
        rated_filter=rated_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        rank_filter=rank_filter,
    )
    return templates.TemplateResponse(
        "partials/tracks_table_body.html", {"request": request, "tracks": tracks}
    )


@app.get("/")
def read_root(
    request: Request,
    db: Session = Depends(get_db),
    rated_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
):
    tracks = crud.get_tracks(
        db,
        rated_filter=rated_filter,
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

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tracks": tracks,
            "all_producers": all_producers,
            "all_voicebanks": all_voicebanks,
        },
    )


@app.post("/rate/{track_id}/delete")
def delete_rating_endpoint(track_id: int, db: Session = Depends(get_db)):
    crud.delete_rating(db, track_id=track_id)
    # Return a 204 No Content response, which is standard for successful actions with no body
    return Response(status_code=204)


@app.post("/rate/{track_id}")
def rate_track(track_id: int, rating: int = Form(...), db: Session = Depends(get_db)):
    crud.create_rating(db, track_id=track_id, rating=rating)
    # You can also return 204 here, or the new rating object if you want
    return Response(status_code=204)
