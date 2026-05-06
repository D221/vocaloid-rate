import json

from app import models


def test_restore_ratings_rejects_invalid_json(client_factory, user):
    client = client_factory(current_user=user)

    response = client.post(
        "/api/restore/ratings",
        files={"file": ("ratings.json", b"{", "application/json")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid JSON file."


def test_restore_ratings_creates_missing_track(client_factory, db_session, user):
    client = client_factory(current_user=user)
    payload = [
        {
            "link": "https://example.com/new-backup",
            "title": "From Backup",
            "producer": "Producer Z",
            "voicebank": "IA",
            "published_date": "2026-01-01T00:00:00+00:00",
            "title_jp": None,
            "producer_jp": None,
            "voicebank_jp": None,
            "image_url": None,
            "rating": 10,
            "notes": "best",
        }
    ]

    response = client.post(
        "/api/restore/ratings",
        files={
            "file": ("ratings.json", json.dumps(payload).encode(), "application/json")
        },
    )

    assert response.status_code == 200
    assert response.json() == {"created": 1, "updated": 0}
    assert (
        db_session.query(models.Track)
        .filter(models.Track.link == "https://example.com/new-backup")
        .first()
        is not None
    )


def test_restore_ratings_rejects_invalid_rating_value(client_factory, user):
    client = client_factory(current_user=user)
    payload = [
        {
            "link": "https://example.com/new-backup",
            "title": "From Backup",
            "producer": "Producer Z",
            "voicebank": "IA",
            "published_date": "2026-01-01T00:00:00+00:00",
            "title_jp": None,
            "producer_jp": None,
            "voicebank_jp": None,
            "image_url": None,
            "rating": 99,
            "notes": None,
        }
    ]

    response = client.post(
        "/api/restore/ratings",
        files={
            "file": ("ratings.json", json.dumps(payload).encode(), "application/json")
        },
    )

    assert response.status_code == 400


def test_js_translations_endpoint_falls_back_to_english(client_factory):
    client = client_factory()

    response = client.get("/api/translations", params={"locale": "fr"})

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_playlist_snapshot_for_playlist_endpoint(
    client_factory, user, playlist, sample_tracks
):
    client = client_factory(current_user=user)

    response = client.get(
        f"/api/playlist/{playlist.id}/playlist-snapshot",
        params={"limit": "1"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {"id": str(sample_tracks[0].id), "page": 1},
        {"id": str(sample_tracks[1].id), "page": 2},
    ]
