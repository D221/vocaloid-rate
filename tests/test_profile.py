import re

from app import auth, main, models




def test_registration_assigns_unique_username(client_factory, db_session, monkeypatch):
    client = client_factory()
    monkeypatch.setattr(auth, "get_secret_key", lambda: "test-secret")
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(main, "should_use_secure_cookies", lambda: False)

    response = client.post(
        "/users/",
        json={"email": "profile_test@example.com", "password": "secret"},
    )
    assert response.status_code == 200
    user = db_session.query(models.User).filter_by(email="profile_test@example.com").first()
    assert user is not None
    assert user.username is not None
    assert user.username == "profile_test"
    assert not user.is_profile_public

def test_update_profile_settings(client_factory, db_session, monkeypatch):
    client = client_factory()
    monkeypatch.setattr(auth, "get_secret_key", lambda: "test-secret")
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(main, "should_use_secure_cookies", lambda: False)

    # Register and automatically login via set-cookie
    client.post(
        "/users/",
        json={"email": "update_test@example.com", "password": "secret"},
    )
    
    # Update profile
    response = client.put(
        "/api/users/me/profile",
        json={"username": "CoolUser", "is_profile_public": True}
    )
    assert response.status_code == 204

    db_session.commit()
    user = db_session.query(models.User).filter_by(email="update_test@example.com").first()
    assert user.username == "CoolUser"
    assert user.is_profile_public is True

def test_public_profile_visibility(client_factory, db_session, monkeypatch):
    client = client_factory()
    monkeypatch.setattr(auth, "get_secret_key", lambda: "test-secret")
    monkeypatch.setattr(main, "is_local_auth_mode", lambda: False)
    monkeypatch.setattr(main, "should_use_secure_cookies", lambda: False)

    # Register
    client.post(
        "/users/",
        json={"email": "vis_test@example.com", "password": "secret"},
    )

    user = db_session.query(models.User).filter_by(email="vis_test@example.com").first()
    username = user.username

    # By default, private. Accessing the profile without being logged in should return 403
    client.cookies.clear()
    response = client.get(f"/user/{username}")
    assert response.status_code == 403

    # Update to public
    user.is_profile_public = True
    db_session.commit()

    # Now it should be accessible
    response = client.get(f"/user/{username}")
    assert response.status_code == 200
    assert "Highly Rated Tracks" in response.text


def test_profile_formats_whole_number_track_ratings_without_decimal(
    client_factory, db_session, user, sample_tracks
):
    user.username = "rating_display"
    user.is_profile_public = True
    db_session.add(
        models.Rating(track_id=sample_tracks[0].id, user_id=user.id, rating=10.0)
    )
    db_session.commit()
    client = client_factory(optional_user=user)

    response = client.get("/user/rating_display")

    assert response.status_code == 200
    assert re.search(r"10\s+★", response.text)
    assert "10.0 ★" not in response.text
