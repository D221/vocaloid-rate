import re

from app.services import scraping as scraping_service


def test_root_loads_when_unauthenticated(client_factory):
    client = client_factory()

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 200


def test_root_renders_track_listing_for_authenticated_user(
    client_factory,
    user,
    sample_tracks,
):
    client = client_factory(optional_user=user)

    response = client.get("/")

    assert response.status_code == 200
    assert "First Track" in response.text
    assert "Second Track" in response.text


def test_root_defaults_to_paginated_limit(client_factory):
    client = client_factory()

    response = client.get("/")

    assert response.status_code == 200
    assert 'data-initial-limit="100"' in response.text


def test_root_respects_explicit_all_limit(client_factory):
    client = client_factory()

    response = client.get("/?limit=all")

    assert response.status_code == 200
    assert 'data-initial-limit="all"' in response.text


def test_root_shows_scraping_page_when_initial_scrape_is_running(
    client_factory,
    monkeypatch,
    user,
):
    client = client_factory(optional_user=user)
    monkeypatch.setattr(scraping_service, "initial_scrape_in_progress", True)

    response = client.get("/")

    assert response.status_code == 200
    assert "scrap" in response.text.lower()


def test_rated_tracks_page_renders_existing_rating(
    client_factory,
    db_session,
    user,
    sample_tracks,
):
    rating = 8
    from app import models

    db_session.add(
        models.Rating(track_id=sample_tracks[0].id, user_id=user.id, rating=rating)
    )
    db_session.commit()

    client = client_factory(optional_user=user)
    response = client.get("/rated_tracks")

    assert response.status_code == 200
    assert "First Track" in response.text


def test_recently_added_excludes_old_tracks(client_factory, user, sample_tracks):
    client = client_factory(optional_user=user)

    response = client.get("/recently_added")

    assert response.status_code == 200
    assert "First Track" in response.text
    assert "Second Track" in response.text
    assert "Old Track" not in response.text


def test_recently_added_page_bounds_initial_render(client_factory, db_session):
    from datetime import datetime, timedelta, timezone

    from app import crud

    now = datetime.now(timezone.utc)
    for i in range(105):
        crud.create_track(
            db_session,
            {
                "title": f"Bulk Track {i}",
                "producer": "Producer A",
                "voicebank": "Miku",
                "published_date": now - timedelta(days=1),
                "link": f"https://example.com/bulk-{i}",
                "title_jp": "",
                "producer_jp": "",
                "voicebank_jp": "",
                "image_url": None,
                "rank": None,
            },
        )

    client = client_factory()
    response = client.get("/recently_added")

    assert response.status_code == 200
    assert len(re.findall(r"<tr\s+data-track-id=", response.text)) == 100
    assert 'data-initial-limit="100"' in response.text
    assert 'data-initial-total-pages="2"' in response.text


def test_recently_added_page_honors_limit_param(client_factory, db_session):
    from datetime import datetime, timedelta, timezone

    from app import crud

    now = datetime.now(timezone.utc)
    for i in range(30):
        crud.create_track(
            db_session,
            {
                "title": f"Small Track {i}",
                "producer": "Producer A",
                "voicebank": "Miku",
                "published_date": now - timedelta(days=1),
                "link": f"https://example.com/small-{i}",
                "title_jp": "",
                "producer_jp": "",
                "voicebank_jp": "",
                "image_url": None,
                "rank": None,
            },
        )

    client = client_factory()
    response = client.get("/recently_added", params={"limit": "25"})

    assert response.status_code == 200
    assert len(re.findall(r"<tr\s+data-track-id=", response.text)) == 25
    assert 'data-initial-limit="25"' in response.text
    assert 'data-initial-total-pages="2"' in response.text


def test_playlist_detail_page_accessible_to_others_if_public(
    client_factory,
    db_session,
    playlist,
):
    playlist.is_public = True
    db_session.commit()
    other_user = type("User", (), {"id": 999, "email": "other@example.com"})()
    client = client_factory(optional_user=other_user)

    response = client.get(f"/playlist/{playlist.id}")

    assert response.status_code == 200
