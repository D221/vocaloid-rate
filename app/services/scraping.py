import logging
import os

from sqlalchemy.orm import Session

from app import crud, models, scraper
from app.constants import SCRAPE_STATUS_FILE
from app.database import SessionLocal

initial_scrape_in_progress = False


def is_initial_scrape_in_progress() -> bool:
    return initial_scrape_in_progress


def set_initial_scrape_in_progress(in_progress: bool) -> None:
    global initial_scrape_in_progress
    initial_scrape_in_progress = in_progress


def write_scrape_status(status_text: str) -> None:
    try:
        status_dir = os.path.dirname(SCRAPE_STATUS_FILE)
        if status_dir and not os.path.exists(status_dir):
            try:
                os.makedirs(status_dir, exist_ok=True)
            except OSError:
                pass

        with open(SCRAPE_STATUS_FILE, "w", encoding="utf-8") as file_handle:
            file_handle.write(status_text)
    except Exception as exc:
        logging.debug("Could not write scrape status to file: %s", exc)


def read_scrape_status() -> str:
    if not os.path.exists(SCRAPE_STATUS_FILE):
        return "idle"

    try:
        with open(SCRAPE_STATUS_FILE, "r", encoding="utf-8") as file_handle:
            return file_handle.read().strip()
    except Exception:
        return "error"


def _get_db_session() -> Session:
    return SessionLocal()


def initial_scrape_task() -> None:
    db = _get_db_session()
    try:
        logging.info("Initial Scrape: Starting full scrape.")
        final_status = "completed"
        try:
            new_tracks_count = 0
            all_scraped_tracks = []
            for page in range(1, 7):
                write_scrape_status(f"in_progress:{page}/6")
                all_scraped_tracks.extend(scraper._scrape_single_page(page))

            logging.info(
                "Full scrape finished. Found %s tracks. Adding to database...",
                len(all_scraped_tracks),
            )

            for track_data in all_scraped_tracks:
                existing_track = crud.get_track_by_link(db, track_data["link"])
                if existing_track:
                    logging.info(
                        "Track with link %s already exists. Skipping.",
                        track_data["link"],
                    )
                else:
                    db_track = models.Track(**track_data)
                    db.add(db_track)
                    new_tracks_count += 1

            logging.info("Added %s new tracks.", new_tracks_count)
            logging.info("Committing all changes to the database...")
            db.commit()
            crud.create_update_log(db)
            logging.info("Database commit successful and update time logged.")

        finally:
            write_scrape_status(final_status)
            set_initial_scrape_in_progress(False)
    finally:
        db.close()


def scrape_and_populate_task() -> None:
    db = _get_db_session()
    try:
        logging.info("Smart Scrape: Checking page 1 for changes...")
        scraped_page_1 = scraper._scrape_single_page(1)
        if not scraped_page_1:
            raise Exception("Failed to scrape page 1.")

        scraped_ranks_list = sorted(
            [(track["rank"], track["link"]) for track in scraped_page_1]
        )

        db_top_50 = (
            db.query(models.Track).filter(models.Track.rank.between(1, 50)).all()
        )
        db_ranks_list = sorted([(track.rank, track.link) for track in db_top_50])

        if scraped_ranks_list == db_ranks_list:
            logging.info(
                "Smart Scrape: No changes found on page 1. The ranking is already up-to-date."
            )
            write_scrape_status("no_changes")
            return

        logging.info("Smart Scrape: Changes detected! Proceeding with full scrape.")
        write_scrape_status("in_progress:1/6")

        final_status = "completed"
        try:
            remaining_pages_tracks = []
            for page in range(2, 7):
                write_scrape_status(f"in_progress:{page}/6")
                remaining_pages_tracks.extend(scraper._scrape_single_page(page))

            all_scraped_tracks = scraped_page_1 + remaining_pages_tracks
            logging.info(
                "Full scrape finished. Found %s tracks. Processing database...",
                len(all_scraped_tracks),
            )

            logging.info("Resetting all track ranks to NULL...")
            db.query(models.Track).update({"rank": None})

            scraped_links = [track["link"] for track in all_scraped_tracks]
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
                            "UPDATED: '%s' (Rank is now %s)",
                            track_data["title"],
                            track_data["rank"],
                        )
                        updated_tracks_count += 1
                else:
                    db_track = models.Track(**track_data)
                    db.add(db_track)
                    logging.info(
                        "ADDED: '%s' (Rank %s)",
                        track_data["title"],
                        track_data["rank"],
                    )
                    new_tracks_count += 1

            logging.info("--- Scrape Summary ---")
            logging.info("New tracks added: %s", new_tracks_count)
            logging.info("Existing tracks updated: %s", updated_tracks_count)

            logging.info("Committing all changes to the database...")
            db.commit()
            crud.create_update_log(db)
            logging.info("Database commit successful and update time logged.")

        except Exception as exc:
            final_status = "error"
            logging.error(
                "An error occurred in the scrape task: %s", exc, exc_info=True
            )
            db.rollback()

        finally:
            write_scrape_status(final_status)
    finally:
        db.close()
