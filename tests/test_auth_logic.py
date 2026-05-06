from datetime import timedelta

import pytest
from fastapi import HTTPException
from jose import jwt
from starlette.requests import Request

from app import auth, crud, schemas
from app.security import ALGORITHM


def make_request_with_cookie(token: str | None = None) -> Request:
    headers = []
    if token is not None:
        headers.append((b"cookie", f"access_token={token}".encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": headers,
    }
    return Request(scope)


def test_password_hash_round_trip():
    hashed = auth.get_password_hash("secret123")

    assert hashed != "secret123"
    assert auth.verify_password("secret123", hashed) is True
    assert auth.verify_password("wrong", hashed) is False


def test_authenticate_user_success_and_failures(db_session):
    user = crud.create_user(
        db_session,
        schemas.UserCreate(email="auth@example.com", password="secret123"),
    )

    assert auth.authenticate_user(db_session, user.email, "secret123") == user
    assert auth.authenticate_user(db_session, user.email, "wrong") is False
    assert (
        auth.authenticate_user(db_session, "missing@example.com", "secret123") is False
    )


def test_create_access_token_requires_secret(monkeypatch):
    monkeypatch.setattr(auth, "get_secret_key", lambda: None)

    with pytest.raises(HTTPException) as exc_info:
        auth.create_access_token({"sub": "user@example.com"})

    assert exc_info.value.status_code == 500


def test_create_access_token_encodes_subject(monkeypatch):
    monkeypatch.setattr(auth, "get_secret_key", lambda: "test-secret")

    token = auth.create_access_token(
        {"sub": "user@example.com"},
        expires_delta=timedelta(minutes=5),
    )
    payload = jwt.decode(token, "test-secret", algorithms=[ALGORITHM])

    assert payload["sub"] == "user@example.com"
    assert "exp" in payload


@pytest.mark.anyio
async def test_get_current_user_from_cookie(db_session, monkeypatch):
    user = crud.create_user(
        db_session,
        schemas.UserCreate(email="cookie@example.com", password="secret123"),
    )
    monkeypatch.setattr(auth, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(auth, "get_secret_key", lambda: "test-secret")
    token = auth.create_access_token({"sub": user.email})

    resolved = await auth.get_current_user(
        make_request_with_cookie(token),
        None,
        db_session,
    )

    assert resolved.email == user.email


@pytest.mark.anyio
async def test_get_current_user_rejects_missing_or_invalid_token(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(auth, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(auth, "get_secret_key", lambda: "test-secret")

    with pytest.raises(HTTPException) as missing_exc:
        await auth.get_current_user(make_request_with_cookie(None), None, db_session)
    assert missing_exc.value.status_code == 401

    with pytest.raises(HTTPException) as invalid_exc:
        await auth.get_current_user(
            make_request_with_cookie("bad-token"),
            None,
            db_session,
        )
    assert invalid_exc.value.status_code == 401


@pytest.mark.anyio
async def test_get_optional_current_user_returns_none_for_invalid_cases(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(auth, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(auth, "get_secret_key", lambda: "test-secret")

    assert (
        await auth.get_optional_current_user(
            make_request_with_cookie(None),
            None,
            db_session,
        )
        is None
    )
    assert (
        await auth.get_optional_current_user(
            make_request_with_cookie("bad-token"),
            None,
            db_session,
        )
        is None
    )


def test_get_or_create_local_user_creates_and_promotes_admin(db_session):
    user = auth.get_or_create_local_user(db_session)
    second = auth.get_or_create_local_user(db_session)

    assert user.email == auth.LOCAL_DEFAULT_EMAIL
    assert user.is_admin is True
    assert second.id == user.id


@pytest.mark.anyio
async def test_local_mode_current_user_uses_local_user(db_session, monkeypatch):
    monkeypatch.setattr(auth, "is_local_auth_mode", lambda: True)

    user = await auth.get_current_user(make_request_with_cookie(None), None, db_session)

    assert user.email == auth.LOCAL_DEFAULT_EMAIL
