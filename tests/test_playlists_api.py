from app import models


def test_create_update_and_delete_playlist(client_factory, db_session, user):
    client = client_factory(current_user=user)

    create_response = client.post(
        "/api/playlists",
        json={"name": "Chill", "description": "Late night"},
    )

    assert create_response.status_code == 200
    playlist_id = create_response.json()["id"]
    assert create_response.json()["is_public"] is True

    update_response = client.put(
        f"/api/playlists/{playlist_id}",
        json={
            "name": "Chill Updated",
            "description": "Edited",
            "is_public": False,
        },
    )
    delete_response = client.delete(f"/api/playlists/{playlist_id}")

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Chill Updated"
    assert update_response.json()["is_public"] is False
    assert delete_response.status_code == 200
    assert (
        db_session.query(models.Playlist)
        .filter(models.Playlist.id == playlist_id)
        .first()
        is None
    )


def test_add_remove_and_reorder_playlist_tracks(
    client_factory,
    db_session,
    user,
    playlist,
    sample_tracks,
):
    client = client_factory(current_user=user)

    add_response = client.post(
        f"/api/playlists/{playlist.id}/tracks/{sample_tracks[2].id}"
    )
    reorder_response = client.post(
        f"/api/playlists/{playlist.id}/reorder",
        json=[sample_tracks[2].id, sample_tracks[0].id, sample_tracks[1].id],
    )
    remove_response = client.delete(
        f"/api/playlists/{playlist.id}/tracks/{sample_tracks[0].id}"
    )

    assert add_response.status_code == 200
    assert reorder_response.status_code == 200
    assert remove_response.status_code == 200

    associations = (
        db_session.query(models.PlaylistTrack)
        .filter(models.PlaylistTrack.playlist_id == playlist.id)
        .order_by(models.PlaylistTrack.position.asc())
        .all()
    )
    assert [item.track_id for item in associations] == [
        sample_tracks[2].id,
        sample_tracks[1].id,
    ]


def test_export_single_playlist_returns_tracks(client_factory, user, playlist):
    client = client_factory(current_user=user)

    response = client.get(f"/api/playlists/{playlist.id}/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Favorites"
    assert payload["is_public"] is True
    assert len(payload["tracks"]) == 2
