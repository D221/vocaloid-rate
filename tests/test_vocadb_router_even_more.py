from app import models
from app.routers import vocadb as vocadb_router


def test_artist_search_endpoint_returns_null_when_not_found(
    client_factory, monkeypatch
):
    client = client_factory()
    monkeypatch.setattr(vocadb_router.vocadb, "search_artist", lambda producer: None)

    response = client.get("/api/vocadb_artist_search", params={"producer": "Missing"})

    assert response.status_code == 200
    assert response.json() == {"url": None}


def test_vocadb_lyrics_cached_endpoint_prefers_cache(
    client_factory, db_session, sample_tracks
):
    db_session.add(
        models.Lyric(
            track_id=sample_tracks[0].id,
            language="Japanese",
            translation_type="Original",
            source="VocaDB",
            url="https://vocadb.net/lyrics/1",
            content="cached",
        )
    )
    db_session.commit()
    client = client_factory()

    response = client.get(
        "/api/vocadb_lyrics/123",
        params={"track_id": sample_tracks[0].id},
    )

    assert response.status_code == 200
    assert response.json()["lyrics"][0]["text"] == "cached"


def test_vocadb_lyrics_endpoint_sorts_english_first_for_non_japanese_locale(
    client_factory,
    monkeypatch,
):
    client = client_factory()
    monkeypatch.setattr(
        vocadb_router.vocadb,
        "fetch_lyrics",
        lambda song_id: [
            {
                "label": "Japanese (Original)",
                "text": "jp",
                "source": "VocaDB",
                "url": "u1",
                "translation_type": "Original",
                "language": "Japanese",
            },
            {
                "label": "English (Translation)",
                "text": "en",
                "source": "VocaDB",
                "url": "u2",
                "translation_type": "Translation",
                "language": "English",
            },
        ],
    )

    response = client.get("/api/vocadb_lyrics/123")

    assert response.status_code == 200
    assert response.json()["lyrics"][0]["label"] == "English (Translation)"
