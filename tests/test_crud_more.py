from datetime import datetime, timezone

from app import crud, models


def test_get_tracks_supports_filters_sorting_and_playlist_flag(
    db_session, user, sample_tracks, playlist
):
    db_session.add(
        models.Rating(track_id=sample_tracks[1].id, user_id=user.id, rating=10)
    )
    db_session.commit()

    tracks = crud.get_tracks(
        db_session,
        user_id=user.id,
        rated_filter="rated",
        sort_by="rating",
        sort_dir="desc",
        rank_filter="all",
    )

    assert [track.title for track in tracks] == ["Second Track"]
    assert tracks[0].is_in_playlist is True


def test_get_tracks_count_supports_exact_rating_and_filters(
    db_session, user, sample_tracks
):
    db_session.add_all(
        [
            models.Rating(track_id=sample_tracks[0].id, user_id=user.id, rating=8),
            models.Rating(track_id=sample_tracks[1].id, user_id=user.id, rating=9),
        ]
    )
    db_session.commit()

    count = crud.get_tracks_count(
        db_session,
        user_id=user.id,
        exact_rating_filter=9,
        producer_filter="Producer B",
        rank_filter="all",
    )

    assert count == 1


def test_get_recently_added_tracks_filters_by_title_and_voicebank(
    db_session, sample_tracks
):
    tracks = crud.get_recently_added_tracks(
        db_session,
        title_filter="Second",
        voicebank_filter="Luka",
    )

    assert [track.title for track in tracks] == ["Second Track"]


def test_get_playlist_tracks_filtered_and_count(db_session, user, playlist):
    tracks = crud.get_playlist_tracks_filtered(
        db_session,
        playlist_id=playlist.id,
        user_id=user.id,
        title_filter="First",
    )
    count = crud.get_playlist_tracks_count(
        db_session,
        playlist_id=playlist.id,
        user_id=user.id,
        title_filter="First",
    )

    assert [track.title for track in tracks] == ["First Track"]
    assert count == 1


def test_get_playlist_snapshot_for_playlist_respects_manual_order(
    db_session,
    user,
    playlist,
    sample_tracks,
):
    snapshot = crud.get_playlist_snapshot_for_playlist(
        db_session,
        playlist_id=playlist.id,
        user_id=user.id,
        limit="1",
    )

    assert snapshot == [
        {"id": str(sample_tracks[0].id), "page": 1},
        {"id": str(sample_tracks[1].id), "page": 2},
    ]


def test_get_recently_added_snapshot_respects_filters(db_session, sample_tracks):
    snapshot = crud.get_recently_added_snapshot(
        db_session,
        title_filter="First",
    )

    assert snapshot == [{"id": str(sample_tracks[0].id), "page": 1}]


def test_create_and_update_track_round_trip(db_session):
    track = crud.create_track(
        db_session,
        {
            "title": "Created",
            "producer": "Producer X",
            "voicebank": "IA",
            "published_date": datetime.now(timezone.utc),
            "link": "https://example.com/create",
            "title_jp": "",
            "producer_jp": "",
            "voicebank_jp": "",
            "image_url": None,
            "rank": 50,
        },
    )
    updated = crud.update_track(db_session, track, {"title": "Updated"})

    assert (
        crud.get_track_by_link(db_session, "https://example.com/create").id == track.id
    )
    assert updated.title == "Updated"


def test_delete_rating_removes_existing_rating(db_session, user, sample_tracks):
    db_session.add(
        models.Rating(track_id=sample_tracks[0].id, user_id=user.id, rating=7)
    )
    db_session.commit()

    crud.delete_rating(db_session, sample_tracks[0].id, user.id)

    assert (
        db_session.query(models.Rating)
        .filter_by(track_id=sample_tracks[0].id, user_id=user.id)
        .first()
        is None
    )


def test_create_update_log_and_last_update_time(db_session):
    created = crud.create_update_log(db_session)
    fetched = crud.get_last_update_time(db_session)

    assert fetched.id == created.id
