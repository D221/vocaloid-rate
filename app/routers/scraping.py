import os
import sys
from dotenv import load_dotenv

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

load_dotenv()

from app import models  # noqa: E402
from app.auth import get_current_user  # noqa: E402
from app.config import is_local_mode  # noqa: E402
from app.services.scraping import (  # noqa: E402
    read_scrape_status,
    scrape_and_populate_task,
    write_scrape_status,
)

router = APIRouter(tags=["Scraping"])


@router.post("/scrape")
def scrape_and_populate(
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
):
    if not (current_user.is_admin or is_local_mode()):
        raise HTTPException(
            status_code=403, detail="Only admins can trigger scraping in cloud mode."
        )

    write_scrape_status("idle")
    background_tasks.add_task(scrape_and_populate_task)
    return {"message": "Scraping has been started in the background."}


@router.get("/api/cron/scrape")
def cron_scrape(request: Request, background_tasks: BackgroundTasks):
    auth_header = request.headers.get("Authorization")
    cron_secret = os.environ.get("CRON_SECRET")

    if not cron_secret:
        raise HTTPException(
            status_code=503,
            detail="CRON_SECRET is not configured for scheduled scraping.",
        )

    if auth_header != f"Bearer {cron_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    background_tasks.add_task(scrape_and_populate_task)
    return {"message": "Scraping task has been queued."}


@router.get("/api/cron/bot-bsky")
def cron_bot_bsky(request: Request, background_tasks: BackgroundTasks):
    auth_header = request.headers.get("Authorization")
    cron_secret = os.environ.get("CRON_SECRET")

    if not cron_secret:
        raise HTTPException(
            status_code=503,
            detail="CRON_SECRET is not configured for scheduled tasks.",
        )

    if auth_header != f"Bearer {cron_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Define the task to run the bot script
    def run_bot_task():
        import subprocess
        import logging

        logger = logging.getLogger("bot-task")
        logger.info("Starting Bluesky bot background task...")

        try:
            # Capture output to see errors
            result = subprocess.run(
                [sys.executable, "-m", "scripts.bot_daily_top", "--bsky"],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Bot task output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Bot task failed with exit code {e.returncode}")
            logger.error(f"Bot task error output: {e.stderr}")
        except Exception as e:
            logger.error(f"Unexpected error in bot task: {e}")

    background_tasks.add_task(run_bot_task)
    return {"message": "Bluesky bot task has been queued."}


@router.get("/api/scrape-status")
def get_scrape_status():
    return {"status": read_scrape_status()}
