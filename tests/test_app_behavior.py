from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main
import app.auth as auth


@asynccontextmanager
async def noop_lifespan(_app):
    yield


def make_client(monkeypatch):
    main.app.dependency_overrides = {}
    monkeypatch.setattr(main.app.router, "lifespan_context", noop_lifespan)
    return TestClient(main.app)


def override_db():
    yield object()


def override_user():
    return SimpleNamespace(id=1, email="user@example.com", is_admin=False)


def test_local_mode_redirects_login_and_register_pages(monkeypatch):
    client = make_client(monkeypatch)
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: True)

    login_response = client.get("/login", follow_redirects=False)
    register_response = client.get("/register", follow_redirects=False)

    assert login_response.status_code == 307
    assert login_response.headers["location"] == "/"
    assert register_response.status_code == 307
    assert register_response.headers["location"] == "/"


def test_local_mode_disables_login_and_registration_posts(monkeypatch):
    client = make_client(monkeypatch)
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: True)
    main.app.dependency_overrides[main.get_db] = override_db

    login_response = client.post(
        "/token",
        data={"username": "user@example.com", "password": "secret"},
    )
    register_response = client.post(
        "/users/",
        json={"email": "user@example.com", "password": "secret"},
    )

    assert login_response.status_code == 404
    assert login_response.json()["detail"] == "Authentication is disabled in local mode"
    assert register_response.status_code == 404
    assert (
        register_response.json()["detail"] == "Authentication is disabled in local mode"
    )


def test_local_mode_hides_user_status_fragment(monkeypatch):
    client = make_client(monkeypatch)
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: True)
    main.app.dependency_overrides[main.get_optional_current_user] = lambda: None

    response = client.get("/users/me/")

    assert response.status_code == 200
    assert response.text == ""


def test_cloud_login_requires_secret_key_for_token_creation(monkeypatch):
    client = make_client(monkeypatch)
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(
        main,
        "authenticate_user",
        lambda db, email, password: SimpleNamespace(email=email),
    )
    monkeypatch.setattr(auth, "get_secret_key", lambda: None)
    main.app.dependency_overrides[main.get_db] = override_db

    response = client.post(
        "/token",
        data={"username": "user@example.com", "password": "secret"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Server configuration error: SECRET_KEY not set"


def test_logout_clears_auth_cookie(monkeypatch):
    client = make_client(monkeypatch)
    monkeypatch.setattr(main, "should_use_secure_cookies", lambda: False)

    response = client.post("/logout")

    assert response.status_code == 204
    set_cookie = response.headers["set-cookie"]
    assert "access_token=\"\"" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_bulk_playlist_import_rejects_non_list_payload(monkeypatch):
    client = make_client(monkeypatch)
    main.app.dependency_overrides[main.get_db] = override_db
    main.app.dependency_overrides[main.get_current_user] = override_user

    response = client.post(
        "/api/playlists/import",
        files={"file": ("playlists.json", b'{"name":"not-a-list"}', "application/json")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "JSON is not a valid playlists export."


def test_single_playlist_import_rejects_invalid_payload(monkeypatch):
    client = make_client(monkeypatch)
    main.app.dependency_overrides[main.get_db] = override_db
    main.app.dependency_overrides[main.get_current_user] = override_user

    response = client.post(
        "/api/playlists/import-single",
        files={"file": ("playlist.json", b'["not-a-playlist"]', "application/json")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "JSON is not a valid single playlist export."


def test_single_playlist_import_accepts_valid_payload(monkeypatch):
    client = make_client(monkeypatch)
    main.app.dependency_overrides[main.get_db] = override_db
    main.app.dependency_overrides[main.get_current_user] = override_user
    monkeypatch.setattr(main.crud, "import_playlists", lambda db, user_id, data: (1, 0))

    response = client.post(
        "/api/playlists/import-single",
        files={
            "file": (
                "playlist.json",
                b'{"name":"Favorites","tracks":["https://example.com/song"]}',
                "application/json",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "created", "count": 1}
