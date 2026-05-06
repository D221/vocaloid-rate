def test_get_user_playlists_endpoint_returns_list(client_factory, user, playlist):
    client = client_factory(current_user=user)

    response = client.get("/api/playlists")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Favorites"


def test_add_track_to_playlist_returns_404_when_missing(
    client_factory, user, sample_tracks
):
    client = client_factory(current_user=user)

    response = client.post(f"/api/playlists/999/tracks/{sample_tracks[0].id}")

    assert response.status_code == 404


def test_update_playlist_returns_404_when_missing(client_factory, user):
    client = client_factory(current_user=user)

    response = client.put(
        "/api/playlists/999",
        json={"name": "Missing", "description": "x"},
    )

    assert response.status_code == 404


def test_export_all_playlists_returns_payload(client_factory, user, playlist):
    client = client_factory(current_user=user)

    response = client.get("/api/playlists/export")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Favorites"


def test_import_playlists_rejects_invalid_json_format(client_factory, user):
    client = client_factory(current_user=user)

    response = client.post(
        "/api/playlists/import",
        files={"file": ("playlists.json", b"{", "application/json")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid JSON format."


def test_import_playlists_handles_internal_error(client_factory, user, monkeypatch):
    from app.routers import playlists as playlists_router

    client = client_factory(current_user=user)
    monkeypatch.setattr(
        playlists_router.crud,
        "import_playlists",
        lambda db, user_id, data: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    response = client.post(
        "/api/playlists/import",
        files={"file": ("playlists.json", b"[]", "application/json")},
    )

    assert response.status_code == 500


def test_export_single_playlist_returns_404_when_missing(client_factory, user):
    client = client_factory(current_user=user)

    response = client.get("/api/playlists/999/export")

    assert response.status_code == 404


def test_delete_playlist_returns_404_when_missing(client_factory, user):
    client = client_factory(current_user=user)

    response = client.delete("/api/playlists/999")

    assert response.status_code == 404
