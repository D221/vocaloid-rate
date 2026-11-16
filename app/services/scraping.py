import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session

from app import crud, models, scraper
from app.constants import SCRAPE_STATUS_FILE
from app.database import SessionLocal

logger = logging.getLogger(__name__)


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
    except Exception as exc:  # noqa: BLE001 - the status file is best-effort
        logger.debug("Could not write scrape status to file: %s", exc)


def read_scrape_status() -> str:
    if not os.path.exists(SCRAPE_STATUS_FILE):
        return "idle"
    try:
        with open(SCRAPE_STATUS_FILE, "r", encoding="utf-8") as file_handle:
            return file_handle.read().strip()
    except Exception:  # noqa: BLE001 - an unreadable status file means error
        return "error"


def _get_db_session() -> Session:
    return SessionLocal()


def initial_scrape_task() -> None:
    db = _get_db_session()
    try:
        logger.info("Initial Scrape: Starting full scrape.")
        final_status = "completed"
        try:
            new_tracks_count = 0
            all_scraped_tracks = []
            for page in range(1, 7):
                write_scrape_status(f"in_progress:{page}/6")
                all_scraped_tracks.extend(scraper._scrape_single_page(page))

            logger.info(
                "Full scrape finished. Found %s tracks. Adding to database...",
                len(all_scraped_tracks),
            )
            for track_data in all_scraped_tracks:
                existing_track = crud.get_track_by_link(db, track_data["link"])
                if existing_track:
                    crud.update_track(db, existing_track, track_data)
                else:
                    crud.create_track(db, track_data)
                    new_tracks_count += 1
            logger.info("Processed all tracks. Added %s new tracks.", new_tracks_count)
            crud.create_update_log(db)
            logger.info("Update time logged.")
        except Exception:
            final_status = "error"
            logger.exception("An error occurred in the initial scrape task")
            db.rollback()
        finally:
            write_scrape_status(final_status)
            set_initial_scrape_in_progress(False)
    finally:
        db.close()


def scrape_and_populate_task() -> None:
    db = _get_db_session()
    try:
        logger.info("Smart Scrape: Checking page 1 for changes...")
        scraped_page_1 = scraper._scrape_single_page(1)
        if not scraped_page_1:
            raise RuntimeError("Failed to scrape page 1.")

        scraped_ranks_list = sorted(
            [(track["rank"], track["link"]) for track in scraped_page_1]
        )

        db_top_50 = (
            db.query(models.Track).filter(models.Track.rank.between(1, 50)).all()
        )
        db_ranks_list = sorted([(track.rank, track.link) for track in db_top_50])

        if scraped_ranks_list == db_ranks_list:
            logger.info(
                "Smart Scrape: No changes found on page 1. The ranking is already up-to-date."
            )
            write_scrape_status("no_changes")
            return

        logger.info("Smart Scrape: Changes detected! Proceeding with full scrape.")
        # Take a snapshot of current ranks before updating
        logger.info("Taking rank snapshot...")
        current_top_tracks = (
            db.query(models.Track).filter(models.Track.rank.isnot(None)).all()
        )
        for track in current_top_tracks:
            db.add(models.RankHistory(track_id=track.id, rank=track.rank))
        db.commit()

        write_scrape_status("in_progress:1/6")

        final_status = "completed"
        try:
            remaining_pages_tracks = []
            for page in range(2, 7):
                write_scrape_status(f"in_progress:{page}/6")
                remaining_pages_tracks.extend(scraper._scrape_single_page(page))
            all_scraped_tracks = scraped_page_1 + remaining_pages_tracks

            # VALIDATION: Only update DB if we got all 300 tracks (6 pages)
            if len(all_scraped_tracks) < 300:
                logger.error(
                    "Scrape validation failed: Only got %s tracks (expected 300). "
                    "Not updating database to avoid partial data.",
                    len(all_scraped_tracks),
                )
                write_scrape_status("error:incomplete_data")
                return

            logger.info(
                "Full scrape finished. Found %s tracks. Processing database...",
                len(all_scraped_tracks),
            )

            logger.info("Resetting all track ranks to NULL...")
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
                    crud.update_track(db, db_track, track_data)
                    updated_tracks_count += 1
                else:
                    crud.create_track(db, track_data)
                    new_tracks_count += 1

            logger.info("--- Scrape Summary ---")
            logger.info("New tracks added: %s", new_tracks_count)
            logger.info("Existing tracks updated: %s", updated_tracks_count)

            crud.create_update_log(db)
            logger.info("Update time logged.")
        except Exception:
            final_status = "error"
            logger.exception("An error occurred in the scrape task")
            db.rollback()
        finally:
            write_scrape_status(final_status)
    finally:
        db.close()


def historical_scrape_task(date: str) -> None:
    """Scrape historical ranking data for a specific date.

    Args:
        date: Date string in YYYY-MM-DD format (e.g., "2026-07-23")
    """
    db = _get_db_session()
    try:
        logger.info(f"Historical Scrape: Starting scrape for date {date}.")
        all_scraped_tracks = []

        # Scrape all 6 pages for the historical date
        for page in range(1, 7):
            logger.info(f"Fetching historical page {page} for date {date}...")
            page_tracks = scraper._scrape_single_page(page, date=date)
            all_scraped_tracks.extend(page_tracks)

        logger.info(
            f"Historical scrape for {date} finished. Found %s tracks.",
            len(all_scraped_tracks),
        )

        # Store historical ranks in RankHistory
        for track_data in all_scraped_tracks:
            existing_track = crud.get_track_by_link(db, track_data["link"])
            if existing_track:
                # Add to rank history with historical date
                historical_date = datetime.strptime(date, "%Y-%m-%d")
                db.add(
                    models.RankHistory(
                        track_id=existing_track.id,
                        rank=track_data["rank"],
                        recorded_at=historical_date,
                    )
                )

        db.commit()
        logger.info(f"Historical data for {date} saved to RankHistory.")
    except Exception:
        logger.exception(
            f"An error occurred in the historical scrape task for {date}",
        )
        db.rollback()
    finally:
        db.close()
