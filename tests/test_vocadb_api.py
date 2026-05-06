from app import models
from app.routers import vocadb as vocadb_router


def test_cached_lyrics_are_returned_without_external_fetch(
    client_factory,
    db_session,
    sample_tracks,
    monkeypatch,
):
    db_session.add_all(
        [
            models.Lyric(
                track_id=sample_tracks[0].id,
                language="Japanese",
                translation_type="Original",
                source="VocaDB",
                url="https://vocadb.net/1",
                content="jp lyrics",
            ),
            models.Lyric(
                track_id=sample_tracks[0].id,
                language="English",
                translation_type="Translation",
                source="VocaDB",
                url="https://vocadb.net/2",
                content="en lyrics",
            ),
        ]
    )
    db_session.commit()
    client = client_factory()

    called = {"fetch": False}
    monkeypatch.setattr(
        vocadb_router.vocadb,
        "fetch_lyrics",
        lambda song_id: called.update(fetch=True),
    )

    response = client.get(f"/api/lyrics/{sample_tracks[0].id}")

    assert response.status_code == 200
    payload = response.json()["lyrics"]
    assert payload[0]["label"] == "English (Translation)"
    assert called["fetch"] is False


def test_smart_lyrics_fetches_and_caches_when_missing(
    client_factory,
    db_session,
    sample_tracks,
    monkeypatch,
):
    client = client_factory()
    monkeypatch.setattr(
        vocadb_router.vocadb,
        "search_song",
        lambda producer, title_en, title_jp: {"song_id": 42},
    )
    monkeypatch.setattr(
        vocadb_router.vocadb,
        "fetch_lyrics",
        lambda song_id: [
            {
                "label": "English (Translation)",
                "text": "translated lyrics",
                "source": "VocaDB",
                "url": "https://vocadb.net/42",
                "language": "English",
                "translation_type": "Translation",
            }
        ],
    )

    response = client.get(f"/api/lyrics/{sample_tracks[1].id}")

    assert response.status_code == 200
    assert response.json()["lyrics"][0]["text"] == "translated lyrics"
    cached = (
        db_session.query(models.Lyric)
        .filter(models.Lyric.track_id == sample_tracks[1].id)
        .all()
    )
    assert len(cached) == 1


def test_vocadb_lyrics_returns_empty_when_no_song_found(
    client_factory,
    sample_tracks,
    monkeypatch,
):
    client = client_factory()
    monkeypatch.setattr(
        vocadb_router.vocadb,
        "search_song",
        lambda producer, title_en, title_jp: {},
    )

    response = client.get(f"/api/lyrics/{sample_tracks[2].id}")

    assert response.status_code == 200
    assert response.json() == {"lyrics": []}
