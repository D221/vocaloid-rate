from app import models


def test_rate_and_delete_rating(client_factory, db_session, user, sample_tracks):
    client = client_factory(current_user=user)

    rate_response = client.post(
        f"/rate/{sample_tracks[0].id}",
        data={"rating": "9", "notes": "great"},
    )
    delete_response = client.post(f"/rate/{sample_tracks[0].id}/delete")

    assert rate_response.status_code == 204
    assert delete_response.status_code == 204
    assert (
        db_session.query(models.Rating)
        .filter(
            models.Rating.track_id == sample_tracks[0].id,
            models.Rating.user_id == user.id,
        )
        .first()
        is None
    )


def test_get_tracks_partial_returns_rendered_table(client_factory, user, sample_tracks):
    client = client_factory(current_user=user)

    response = client.get("/_/get_tracks", params={"limit": "25"})

    assert response.status_code == 200
    payload = response.json()
    assert "table_body_html" in payload
    assert "First Track" in payload["table_body_html"]
    assert payload["pagination"]["total_tracks"] == 2


def test_get_tracks_partial_supports_rated_filter_and_rating_sort(
    client_factory,
    db_session,
    user,
    sample_tracks,
):
    db_session.add(
        models.Rating(track_id=sample_tracks[1].id, user_id=user.id, rating=9)
    )
    db_session.commit()
    client = client_factory(current_user=user)

    response = client.get("/_/get_tracks", params={"rated_filter": "rated"})

    assert response.status_code == 200
    assert "Second Track" in response.json()["table_body_html"]


def test_playlist_tracks_partial_rejects_non_owner(
    client_factory,
    playlist,
):
    other_user = type("User", (), {"id": 999, "email": "other@example.com"})()
    client = client_factory(current_user=other_user)

    response = client.get(f"/api/playlist/{playlist.id}/get_tracks")

    assert response.status_code == 403


def test_playlist_tracks_partial_returns_html(
    client_factory,
    user,
    playlist,
):
    client = client_factory(current_user=user)

    response = client.get(f"/api/playlist/{playlist.id}/get_tracks")

    assert response.status_code == 200
    assert "First Track" in response.json()["table_body_html"]


def test_recently_added_tracks_partial_honors_filter(client_factory, sample_tracks):
    client = client_factory()

    response = client.get(
        "/_/get_recently_added_tracks_partial",
        params={"producer_filter": "Producer B"},
    )

    assert response.status_code == 200
    body = response.json()["table_body_html"]
    assert "Second Track" in body
    assert "First Track" not in body


def test_playlist_snapshot_reflects_page_boundaries(
    client_factory,
    user,
    sample_tracks,
):
    client = client_factory(current_user=user)

    response = client.get("/api/playlist-snapshot", params={"limit": "1"})

    assert response.status_code == 200
    assert response.json() == [
        {"id": str(sample_tracks[0].id), "page": 1},
        {"id": str(sample_tracks[1].id), "page": 2},
    ]


def test_recently_added_snapshot_excludes_old_tracks(
    client_factory,
    sample_tracks,
):
    anonymous_user = type("User", (), {"id": 1, "email": "user@example.com"})()
    client = client_factory(current_user=anonymous_user)

    response = client.get("/api/recently-added-snapshot")

    assert response.status_code == 200
    assert response.json() == [
        {"id": str(sample_tracks[0].id), "page": 1},
        {"id": str(sample_tracks[1].id), "page": 1},
    ]


def test_track_playlist_status_partitions_membership(
    client_factory,
    user,
    playlist,
    sample_tracks,
):
    client = client_factory(current_user=user)

    response = client.get(f"/api/tracks/{sample_tracks[0].id}/playlist-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["member_of"][0]["id"] == playlist.id


def test_backup_and_restore_ratings_round_trip(
    client_factory, db_session, user, sample_tracks
):
    db_session.add(
        models.Rating(
            track_id=sample_tracks[0].id,
            user_id=user.id,
            rating=8,
            notes="nice",
        )
    )
    db_session.commit()
    client = client_factory(current_user=user)

    backup_response = client.get("/api/backup/ratings")
    assert backup_response.status_code == 200

    db_session.query(models.Rating).delete()
    db_session.commit()

    restore_response = client.post(
        "/api/restore/ratings",
        files={
            "file": (
                "ratings.json",
                __import__("json").dumps(backup_response.json()).encode(),
                "application/json",
            )
        },
    )

    assert restore_response.status_code == 200
    restored = (
        db_session.query(models.Rating)
        .filter(
            models.Rating.user_id == user.id,
            models.Rating.track_id == sample_tracks[0].id,
        )
        .first()
    )
    assert restored is not None


def test_restore_ratings_rejects_invalid_extension(client_factory, user):
    client = client_factory(current_user=user)

    response = client.post(
        "/api/restore/ratings",
        files={"file": ("ratings.txt", b"{}", "application/json")},
    )

    assert response.status_code == 400
