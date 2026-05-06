def test_login_bad_credentials_returns_401(client_factory, monkeypatch):
    from app import main

    client = client_factory()
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(main, "authenticate_user", lambda db, email, password: False)

    response = client.post(
        "/token",
        data={"username": "user@example.com", "password": "bad"},
    )

    assert response.status_code == 401


def test_register_duplicate_email_returns_400(client_factory, monkeypatch):
    from app import main

    client = client_factory()
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)

    response = client.post(
        "/users/",
        json={"email": "dup@example.com", "password": "secret123"},
    )
    assert response.status_code == 200

    duplicate = client.post(
        "/users/",
        json={"email": "dup@example.com", "password": "secret123"},
    )

    assert duplicate.status_code == 400


def test_users_me_partial_renders_when_not_local(client_factory, user, monkeypatch):
    from app import main

    client = client_factory(optional_user=user)
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)

    response = client.get("/users/me/")

    assert response.status_code == 200
    assert user.email in response.text


def test_register_internal_error_returns_500(client_factory, monkeypatch):
    from app import main
    from app.routers import auth as auth_router

    client = client_factory()
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(
        auth_router.crud,
        "create_user",
        lambda db, user: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    response = client.post(
        "/users/",
        json={"email": "boom@example.com", "password": "secret123"},
    )

    assert response.status_code == 500
