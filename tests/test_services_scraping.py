from pathlib import Path
from datetime import datetime, timezone

from app import models
from app.services import scraping as scraping_service


def test_write_and_read_scrape_status(monkeypatch, tmp_path: Path):
    status_file = tmp_path / "scrape_status.txt"
    monkeypatch.setattr(scraping_service, "SCRAPE_STATUS_FILE", str(status_file))

    scraping_service.write_scrape_status("completed")

    assert scraping_service.read_scrape_status() == "completed"


def test_scrape_and_populate_task_marks_no_changes(
    monkeypatch,
    session_factory,
):
    db = session_factory()
    db.add(
        models.Track(
            title="Track 1",
            producer="Producer A",
            voicebank="Miku",
            published_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            link="https://example.com/a",
            title_jp="",
            producer_jp="",
            voicebank_jp="",
            image_url=None,
            rank=1,
        )
    )
    db.commit()
    db.close()

    statuses = []
    monkeypatch.setattr(scraping_service, "_get_db_session", session_factory)
    monkeypatch.setattr(
        scraping_service.scraper,
        "_scrape_single_page",
        lambda page: [
            {
                "title": "Track 1",
                "producer": "Producer A",
                "voicebank": "Miku",
                "published_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "link": "https://example.com/a",
                "title_jp": "",
                "producer_jp": "",
                "voicebank_jp": "",
                "image_url": None,
                "rank": 1,
            }
        ],
    )
    monkeypatch.setattr(
        scraping_service,
        "write_scrape_status",
        lambda status: statuses.append(status),
    )

    scraping_service.scrape_and_populate_task()

    assert statuses[-1] == "no_changes"


def test_initial_scrape_task_adds_tracks_and_resets_state(monkeypatch, session_factory):
    statuses = []
    monkeypatch.setattr(scraping_service, "_get_db_session", session_factory)
    monkeypatch.setattr(
        scraping_service.scraper,
        "_scrape_single_page",
        lambda page: [
            {
                "title": f"Track {page}",
                "producer": "Producer A",
                "voicebank": "Miku",
                "published_date": datetime(2026, 1, page, tzinfo=timezone.utc),
                "link": f"https://example.com/initial/{page}",
                "title_jp": "",
                "producer_jp": "",
                "voicebank_jp": "",
                "image_url": None,
                "rank": page,
            }
        ],
    )
    monkeypatch.setattr(
        scraping_service,
        "write_scrape_status",
        lambda status: statuses.append(status),
    )
    monkeypatch.setattr(
        scraping_service,
        "set_initial_scrape_in_progress",
        lambda value: statuses.append(f"state:{value}"),
    )

    scraping_service.initial_scrape_task()

    db = session_factory()
    try:
        assert db.query(models.Track).count() == 6
        assert db.query(models.UpdateLog).count() == 1
    finally:
        db.close()
    assert statuses[-2:] == ["completed", "state:False"]


def test_scrape_and_populate_task_updates_and_adds_tracks(monkeypatch, session_factory):
    db = session_factory()
    db.add_all(
        [
            models.Track(
                title="Old Name",
                producer="Producer A",
                voicebank="Miku",
                published_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                link="https://example.com/existing",
                title_jp="",
                producer_jp="",
                voicebank_jp="",
                image_url=None,
                rank=1,
            ),
            models.Track(
                title="Drop Rank",
                producer="Producer B",
                voicebank="Luka",
                published_date=datetime(2026, 1, 2, tzinfo=timezone.utc),
                link="https://example.com/other",
                title_jp="",
                producer_jp="",
                voicebank_jp="",
                image_url=None,
                rank=2,
            ),
        ]
    )
    db.commit()
    db.close()

    statuses = []
    monkeypatch.setattr(scraping_service, "_get_db_session", session_factory)

    def fake_scrape(page: int):
        if page == 1:
            return [
                {
                    "title": "Updated Name",
                    "producer": "Producer A",
                    "voicebank": "Miku",
                    "published_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    "link": "https://example.com/existing",
                    "title_jp": "",
                    "producer_jp": "",
                    "voicebank_jp": "",
                    "image_url": None,
                    "rank": 1,
                }
            ]
        if page == 2:
            return [
                {
                    "title": "Brand New",
                    "producer": "Producer C",
                    "voicebank": "Len",
                    "published_date": datetime(2026, 1, 3, tzinfo=timezone.utc),
                    "link": "https://example.com/new",
                    "title_jp": "",
                    "producer_jp": "",
                    "voicebank_jp": "",
                    "image_url": None,
                    "rank": 2,
                }
            ]
        return []

    monkeypatch.setattr(scraping_service.scraper, "_scrape_single_page", fake_scrape)
    monkeypatch.setattr(
        scraping_service,
        "write_scrape_status",
        lambda status: statuses.append(status),
    )

    scraping_service.scrape_and_populate_task()

    db = session_factory()
    try:
        updated = (
            db.query(models.Track)
            .filter_by(link="https://example.com/existing")
            .first()
        )
        added = db.query(models.Track).filter_by(link="https://example.com/new").first()
        dropped = (
            db.query(models.Track).filter_by(link="https://example.com/other").first()
        )
        assert updated.title == "Updated Name"
        assert added is not None
        assert dropped.rank is None
        assert db.query(models.UpdateLog).count() == 1
    finally:
        db.close()
    assert statuses[-1] == "completed"
