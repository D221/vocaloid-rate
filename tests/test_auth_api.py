import app.auth as auth


def test_login_success_sets_auth_cookie(client_factory, monkeypatch):
    client = client_factory()
    monkeypatch.setattr(auth, "get_secret_key", lambda: "test-secret")
    monkeypatch.setattr(auth, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(
        auth,
        "authenticate_user",
        lambda db, email, password: type("User", (), {"email": email})(),
    )
    monkeypatch.setattr(
        auth.router if hasattr(auth, "router") else auth,
        "authenticate_user",
        lambda db, email, password: type("User", (), {"email": email})(),
        raising=False,
    )

    from app import main

    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(
        main,
        "authenticate_user",
        lambda db, email, password: type("User", (), {"email": email})(),
    )
    monkeypatch.setattr(main, "should_use_secure_cookies", lambda: False)

    response = client.post(
        "/token",
        data={"username": "user@example.com", "password": "secret"},
    )

    assert response.status_code == 204
    assert "access_token=" in response.headers["set-cookie"]


def test_login_accepts_username(client_factory, db_session, monkeypatch):
    from app import main
    from app import schemas

    client = client_factory()
    monkeypatch.setattr(auth, "get_secret_key", lambda: "test-secret")
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(main, "should_use_secure_cookies", lambda: False)
    user = auth.crud.create_user(
        db_session,
        schemas.UserCreate(email="username-login@example.com", password="secret123"),
    )

    response = client.post(
        "/token",
        data={"username": user.username, "password": "secret123"},
    )

    assert response.status_code == 204
    assert "access_token=" in response.headers["set-cookie"]


def test_register_success_creates_user_and_sets_cookie(
    client_factory,
    db_session,
    monkeypatch,
):
    client = client_factory()
    monkeypatch.setattr(auth, "get_secret_key", lambda: "test-secret")

    from app import main, models

    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(main, "should_use_secure_cookies", lambda: False)

    response = client.post(
        "/users/",
        json={"email": "new@example.com", "password": "secret123"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"
    assert "access_token=" in response.headers["set-cookie"]
    assert (
        db_session.query(models.User)
        .filter(models.User.email == "new@example.com")
        .first()
        is not None
    )
