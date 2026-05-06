from app import models
from app.routers import vocadb as vocadb_router


def test_vocadb_artist_search_endpoint_returns_url(client_factory, monkeypatch):
    client = client_factory()
    monkeypatch.setattr(
        vocadb_router.vocadb,
        "search_artist",
        lambda producer: "https://vocadb.net/Ar/1",
    )

    response = client.get(
        "/api/vocadb_artist_search", params={"producer": "Producer A"}
    )

    assert response.status_code == 200
    assert response.json() == {"url": "https://vocadb.net/Ar/1"}


def test_vocadb_search_endpoint_returns_result(client_factory, monkeypatch):
    client = client_factory()
    monkeypatch.setattr(
        vocadb_router.vocadb,
        "search_song",
        lambda producer, title_en, title_jp: {
            "url": "https://vocadb.net/S/1",
            "song_id": 1,
        },
    )

    response = client.get(
        "/api/vocadb_search",
        params={"producer": "Producer A", "title_en": "Song"},
    )

    assert response.status_code == 200
    assert response.json()["song_id"] == 1


def test_vocadb_lyrics_endpoint_returns_empty_for_no_results(
    client_factory, monkeypatch
):
    client = client_factory()
    monkeypatch.setattr(vocadb_router.vocadb, "fetch_lyrics", lambda song_id: [])

    response = client.get("/api/vocadb_lyrics/123")

    assert response.status_code == 200
    assert response.json() == {"lyrics": []}


def test_vocadb_lyrics_endpoint_caches_fetched_lyrics(
    client_factory,
    db_session,
    sample_tracks,
    monkeypatch,
):
    client = client_factory()
    monkeypatch.setattr(
        vocadb_router.vocadb,
        "fetch_lyrics",
        lambda song_id: [
            {
                "label": "English (Translation)",
                "text": "lyrics",
                "source": "VocaDB",
                "url": "https://vocadb.net/lyric/1",
                "translation_type": "Translation",
                "language": "English",
            }
        ],
    )

    response = client.get(
        "/api/vocadb_lyrics/123",
        params={"track_id": sample_tracks[0].id},
    )

    assert response.status_code == 200
    assert (
        db_session.query(models.Lyric)
        .filter(models.Lyric.track_id == sample_tracks[0].id)
        .count()
        == 1
    )
