from datetime import datetime, timedelta


def test_root_handles_invalid_limit_cookie_and_marks_outdated_db(
    client_factory,
    db_session,
    user,
    sample_tracks,
):
    from app import models

    db_session.add(models.UpdateLog(updated_at=datetime.now() - timedelta(days=2)))
    db_session.commit()
    client = client_factory(optional_user=user)
    client.cookies.set("default_page_size", "bad")

    response = client.get("/")

    assert response.status_code == 200


def test_recommendations_page_normalizes_invalid_recent_bias(
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

    response = client.get("/recommendations?recent_bias=weird")

    assert response.status_code == 200
