def test_playlists_page_renders_for_authenticated_user(client_factory, user, playlist):
    client = client_factory(optional_user=user)

    response = client.get("/playlists")

    assert response.status_code == 200
    assert "Favorites" in response.text


def test_playlist_detail_page_renders_for_owner(client_factory, user, playlist):
    client = client_factory(optional_user=user)

    response = client.get(f"/playlist/{playlist.id}")

    assert response.status_code == 200
    assert "Favorites" in response.text
    assert "First Track" in response.text


def test_playlist_edit_page_renders_for_owner(client_factory, user, playlist):
    client = client_factory(optional_user=user)

    response = client.get(f"/playlist/edit/{playlist.id}")

    assert response.status_code == 200
    assert "Favorites" in response.text


def test_options_page_renders(client_factory):
    client = client_factory()

    response = client.get("/options")

    assert response.status_code == 200


def test_producers_index_renders(client_factory, sample_tracks):
    client = client_factory()

    response = client.get("/producers")

    assert response.status_code == 200
    assert "Producer A" in response.text
    assert "Producer B" in response.text


def test_voicebanks_index_renders(client_factory, sample_tracks):
    client = client_factory()

    response = client.get("/voicebanks")

    assert response.status_code == 200
    assert "Miku" in response.text
    assert "Luka" in response.text


def test_entity_page_sorts_tracks_by_newest_first(client_factory, sample_tracks):
    client = client_factory()

    response = client.get("/producer/Producer%20A")

    assert response.status_code == 200
    assert response.text.index("First Track") < response.text.index("Old Track")


def test_entity_page_renders_track_thumbnail(client_factory, db_session, sample_tracks):
    sample_tracks[0].image_url = "https://img.youtube.com/vi/abc123/mqdefault.jpg"
    db_session.commit()
    client = client_factory()

    response = client.get("/producer/Producer%20A")

    assert response.status_code == 200
    assert 'src="https://img.youtube.com/vi/abc123/mqdefault.jpg"' in response.text
    assert 'alt="First Track"' in response.text


def test_recommendations_page_renders_for_authenticated_user(
    client_factory,
    db_session,
    user,
    sample_tracks,
):
    from app import models

    db_session.add(
        models.Rating(track_id=sample_tracks[0].id, user_id=user.id, rating=9)
    )
    db_session.commit()
    client = client_factory(optional_user=user)

    response = client.get("/recommendations?recent_bias=strong")

    assert response.status_code == 200


def test_login_and_register_pages_render_when_not_local(client_factory, monkeypatch):
    from app import main

    client = client_factory()
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)

    login_response = client.get("/login")
    register_response = client.get("/register")

    assert login_response.status_code == 200
    assert register_response.status_code == 200
