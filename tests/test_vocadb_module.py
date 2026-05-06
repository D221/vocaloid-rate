import requests

from app import vocadb


class DummyResponse:
    def __init__(self, payload, should_raise: Exception | None = None):
        self.payload = payload
        self.should_raise = should_raise

    def raise_for_status(self):
        if self.should_raise:
            raise self.should_raise

    def json(self):
        return self.payload


def test_search_artist_returns_profile_url(monkeypatch):
    monkeypatch.setattr(
        vocadb.requests,
        "get",
        lambda url, headers, timeout: DummyResponse({"items": [{"id": 123}]}),
    )

    result = vocadb.search_artist("Producer A")

    assert result == "https://vocadb.net/Ar/123"


def test_search_artist_returns_none_on_request_failure(monkeypatch):
    monkeypatch.setattr(
        vocadb.requests,
        "get",
        lambda url, headers, timeout: DummyResponse(
            {},
            requests.exceptions.RequestException("boom"),
        ),
    )

    assert vocadb.search_artist("Producer A") is None


def test_search_song_uses_japanese_fallback(monkeypatch):
    responses = iter(
        [
            DummyResponse({"items": [{"id": 55}]}),
            DummyResponse({"items": []}),
            DummyResponse({"items": [{"id": 777}]}),
        ]
    )
    monkeypatch.setattr(
        vocadb.requests,
        "get",
        lambda url, headers, timeout: next(responses),
    )

    result = vocadb.search_song("Producer A", "English Title", "Japanese Title")

    assert result == {"url": "https://vocadb.net/S/777", "song_id": 777}


def test_search_song_returns_empty_when_artist_missing(monkeypatch):
    monkeypatch.setattr(
        vocadb.requests,
        "get",
        lambda url, headers, timeout: DummyResponse({"items": []}),
    )

    assert vocadb.search_song("Producer A", "Title") == {"url": None, "song_id": None}


def test_fetch_lyrics_normalizes_labels_and_line_breaks(monkeypatch):
    monkeypatch.setattr(
        vocadb.requests,
        "get",
        lambda url, headers, timeout: DummyResponse(
            {
                "lyrics": [
                    {
                        "value": "a\nb",
                        "cultureCodes": ["ja"],
                        "translationType": "Original",
                        "source": "VocaDB",
                        "url": "https://vocadb.net/lyrics/1",
                    },
                    {
                        "value": "romaji",
                        "cultureCodes": [],
                        "translationType": "Romanized",
                        "source": "VocaDB",
                        "url": "https://vocadb.net/lyrics/2",
                    },
                ]
            }
        ),
    )

    lyrics = vocadb.fetch_lyrics(1)

    assert lyrics[0]["label"] == "Japanese (Original)"
    assert lyrics[0]["text"] == "a<br>b"
    assert lyrics[1]["label"] == "Romaji"


def test_fetch_lyrics_returns_empty_on_failure(monkeypatch):
    monkeypatch.setattr(
        vocadb.requests,
        "get",
        lambda url, headers, timeout: DummyResponse(
            {},
            requests.exceptions.RequestException("boom"),
        ),
    )

    assert vocadb.fetch_lyrics(1) == []
