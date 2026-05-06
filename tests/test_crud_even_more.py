from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app import crud, models


def test_create_rating_rejects_invalid_score(db_session, user, sample_tracks):
    with pytest.raises(ValueError):
        crud.create_rating(db_session, sample_tracks[0].id, user.id, 11)


def test_create_rating_updates_existing_rating(db_session, user, sample_tracks):
    first = crud.create_rating(db_session, sample_tracks[0].id, user.id, 7, "note")
    second = crud.create_rating(db_session, sample_tracks[0].id, user.id, 9, "better")

    assert first.id == second.id
    assert second.rating == 9
    assert second.notes == "better"


def test_create_rating_recovers_from_integrity_error(
    monkeypatch, db_session, user, sample_tracks
):
    state = {"raised": False}
    real_commit = db_session.commit

    def flaky_commit():
        if not state["raised"]:
            state["raised"] = True
            raise IntegrityError("stmt", "params", Exception("orig"))
        return real_commit()

    monkeypatch.setattr(db_session, "commit", flaky_commit)
    existing = models.Rating(track_id=sample_tracks[0].id, user_id=user.id, rating=6)
    db_session.add(existing)
    real_commit()

    rating = crud.create_rating(db_session, sample_tracks[0].id, user.id, 8)

    assert rating.rating == 8


def test_get_rating_statistics_returns_empty_defaults(db_session, user):
    stats = crud.get_rating_statistics(db_session, user.id)

    assert stats == {
        "total_ratings": 0,
        "average_rating": 0,
        "median_rating": 0,
        "top_producers": [],
        "top_voicebanks": [],
        "rating_distribution": {},
    }


def test_delete_update_user_and_get_users(db_session):
    from app import schemas

    user = crud.create_user(
        db_session,
        schemas.UserCreate(email="a@example.com", password="secret123"),
    )

    assert crud.get_user(db_session, user.id).email == "a@example.com"
    assert crud.get_users(db_session)
    updated = crud.update_user_admin_status(db_session, user.id, True)
    assert updated is not None
    assert updated.is_admin is True
    assert crud.delete_user(db_session, user.id) is True
    assert crud.delete_user(db_session, user.id) is False


def test_playlist_mutation_helpers_return_none_or_noop_when_missing(db_session, user):
    assert crud.delete_playlist(db_session, 999, user.id) is False
    assert crud.update_playlist(db_session, 999, user.id, "x", None) is None
    assert crud.add_track_to_playlist(db_session, 999, 1, user.id) is None
    assert crud.export_single_playlist(db_session, 999, user.id) is None
    crud.remove_track_from_playlist(db_session, 999, 1, user.id)
    crud.reorder_playlist(db_session, 999, [1, 2], user.id)


def test_track_playlist_membership_handles_non_member_lists(
    db_session, user, playlist, sample_tracks
):
    other = models.Playlist(user_id=user.id, name="Other", description=None)
    db_session.add(other)
    db_session.commit()
    membership = crud.get_track_playlist_membership(
        db_session, sample_tracks[0].id, user.id
    )

    assert any(item["name"] == "Favorites" for item in membership["member_of"])
    assert any(item["name"] == "Other" for item in membership["not_member_of"])


def test_get_tracks_locale_japanese_filters_and_unranked_sort(db_session, user):
    now = datetime.now(timezone.utc)
    track = models.Track(
        title="English",
        producer="Prod EN",
        voicebank="Miku EN",
        published_date=now,
        link="https://example.com/jp",
        title_jp="日本語",
        producer_jp="プロデューサー",
        voicebank_jp="ミク",
        image_url=None,
        rank=None,
    )
    db_session.add(track)
    db_session.commit()

    results = crud.get_tracks(
        db_session,
        user_id=user.id,
        title_filter="日本",
        producer_filter="プロ",
        voicebank_filter="ミク",
        rank_filter="unranked",
        locale="ja",
    )

    assert [item.id for item in results] == [track.id]


def test_playlist_and_recent_snapshots_cover_sort_branches(
    db_session, user, playlist, sample_tracks
):
    db_session.add(
        models.Rating(track_id=sample_tracks[1].id, user_id=user.id, rating=10)
    )
    db_session.commit()

    playlist_snapshot = crud.get_playlist_snapshot_for_playlist(
        db_session,
        playlist.id,
        user.id,
        limit="1",
        sort_by="title",
        sort_dir="desc",
    )
    global_snapshot = crud.get_playlist_snapshot(
        db_session,
        user_id=user.id,
        limit="1",
        exact_rating_filter=10,
        rank_filter="all",
    )

    assert playlist_snapshot
    assert global_snapshot == [{"id": str(sample_tracks[1].id), "page": 1}]
