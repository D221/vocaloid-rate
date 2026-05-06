import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app import models
from app.auth import get_current_user
from app.config import is_local_mode
from app.services.scraping import (
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


@router.get("/api/scrape-status")
def get_scrape_status():
    return {"status": read_scrape_status()}
