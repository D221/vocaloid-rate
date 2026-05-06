from app import crud, models


def test_import_export_playlists_round_trip(db_session, user, sample_tracks):
    created, updated = crud.import_playlists(
        db_session,
        user_id=user.id,
        data=[
            {
                "name": "Imported",
                "description": "desc",
                "tracks": [sample_tracks[1].link, sample_tracks[0].link],
            }
        ],
    )

    exported = crud.export_playlists(db_session, user.id)

    assert created == 1
    assert updated == 0
    assert exported == [
        {
            "name": "Imported",
            "description": "desc",
            "tracks": [sample_tracks[1].link, sample_tracks[0].link],
        }
    ]


def test_import_playlists_updates_existing_playlist_contents(
    db_session,
    user,
    sample_tracks,
    playlist,
):
    created, updated = crud.import_playlists(
        db_session,
        user_id=user.id,
        data=[
            {
                "name": playlist.name,
                "description": "changed",
                "tracks": [sample_tracks[1].link],
            }
        ],
    )

    exported = crud.export_single_playlist(db_session, playlist.id, user.id)

    assert created == 0
    assert updated == 1
    assert exported == {
        "name": "Favorites",
        "description": "Test playlist",
        "tracks": [sample_tracks[1].link],
    }


def test_rating_statistics_returns_distribution_and_top_entities(
    db_session,
    user,
):
    tracks = []
    for idx, rating in enumerate([9, 8, 7], start=1):
        track = models.Track(
            title=f"Track {idx}",
            producer="Producer A",
            voicebank="Miku",
            published_date=user.id and __import__("datetime").datetime.now(),
            link=f"https://example.com/stats/{idx}",
            title_jp="",
            producer_jp="",
            voicebank_jp="",
            image_url=None,
            rank=idx,
        )
        db_session.add(track)
        db_session.flush()
        db_session.add(models.Rating(track_id=track.id, user_id=user.id, rating=rating))
        tracks.append(track)
    db_session.commit()

    stats = crud.get_rating_statistics(db_session, user.id)

    assert stats["total_ratings"] == 3
    assert stats["average_rating"] == 8.0
    assert stats["median_rating"] == 8
    assert stats["top_producers"][0]["name"] == "Producer A"
    assert stats["top_voicebanks"][0]["name"] == "Miku"
    assert stats["rating_distribution"] == {9.0: 1, 8.0: 1, 7.0: 1}


def test_recommendations_prefer_matching_highly_rated_producer(
    db_session,
    user,
):
    rated_tracks = [
        ("Loved 1", "Producer A", "Miku", 10),
        ("Loved 2", "Producer A", "Miku", 9),
        ("Loved 3", "Producer A", "Miku", 9),
        ("Neutral", "Producer B", "Luka", 5),
    ]
    for idx, (title, producer, voicebank, rating) in enumerate(rated_tracks, start=1):
        track = models.Track(
            title=title,
            producer=producer,
            voicebank=voicebank,
            published_date=__import__("datetime").datetime.now(),
            link=f"https://example.com/reco/rated/{idx}",
            title_jp="",
            producer_jp="",
            voicebank_jp="",
            image_url=None,
            rank=idx,
        )
        db_session.add(track)
        db_session.flush()
        db_session.add(models.Rating(track_id=track.id, user_id=user.id, rating=rating))

    recommended = models.Track(
        title="Should Recommend",
        producer="Producer A",
        voicebank="Miku",
        published_date=__import__("datetime").datetime.now(),
        link="https://example.com/reco/candidate/1",
        title_jp="",
        producer_jp="",
        voicebank_jp="",
        image_url=None,
        rank=10,
    )
    unrecommended = models.Track(
        title="Should Not Recommend",
        producer="Producer C",
        voicebank="Len",
        published_date=__import__("datetime").datetime.now(),
        link="https://example.com/reco/candidate/2",
        title_jp="",
        producer_jp="",
        voicebank_jp="",
        image_url=None,
        rank=11,
    )
    db_session.add_all([recommended, unrecommended])
    db_session.commit()

    recommendations = crud.get_recommended_tracks(db_session, user.id)

    assert recommendations
    assert recommendations[0].title == "Should Recommend"
    assert all(track.title != "Should Not Recommend" for track in recommendations)


def test_playlist_snapshot_filters_unrated_tracks(db_session, user, sample_tracks):
    db_session.add(
        models.Rating(track_id=sample_tracks[0].id, user_id=user.id, rating=8)
    )
    db_session.commit()

    snapshot = crud.get_playlist_snapshot(
        db_session,
        user_id=user.id,
        limit="1",
        rated_filter="unrated",
        rank_filter="all",
        sort_by="published_date",
        sort_dir="desc",
    )

    assert snapshot == [
        {"id": str(sample_tracks[1].id), "page": 1},
        {"id": str(sample_tracks[2].id), "page": 2},
    ]
