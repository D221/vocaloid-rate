import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, vocadb
from app.dependencies import get_db, get_locale

router = APIRouter(tags=["VocaDB"])


def _format_cached_lyrics(cached_lyrics, locale: str) -> list[dict[str, str]]:
    available_lyrics = []
    for lyric in cached_lyrics:
        label = lyric.language + (
            f" ({lyric.translation_type})"
            if lyric.translation_type != "Unknown"
            else ""
        )
        if lyric.translation_type == "Romanized":
            label = "Romaji"
        elif lyric.translation_type == "Translation" and lyric.language == "English":
            label = "English (Translation)"
        elif lyric.translation_type == "Original" and lyric.language == "Japanese":
            label = "Japanese (Original)"

        available_lyrics.append(
            {
                "label": label,
                "text": lyric.content,
                "source": lyric.source,
                "url": lyric.url,
                "translation_type": lyric.translation_type,
            }
        )

    available_lyrics.sort(
        key=lambda lyric: (
            0
            if (locale == "ja" and "Japanese" in lyric["label"])
            or (locale != "ja" and "English" in lyric["label"])
            else 1
            if "Romaji" in lyric["label"]
            else 2
            if (locale == "ja" and "English" in lyric["label"])
            or (locale != "ja" and "Japanese" in lyric["label"])
            else 3
        )
    )
    return available_lyrics


@router.get("/api/lyrics/{track_id}")
def get_smart_lyrics(
    track_id: int,
    db: Session = Depends(get_db),
    locale: str = Depends(get_locale),
):
    cached_lyrics = (
        db.query(models.Lyric).filter(models.Lyric.track_id == track_id).all()
    )
    if cached_lyrics:
        logging.info("Serving cached lyrics for track %s", track_id)
        return {"lyrics": _format_cached_lyrics(cached_lyrics, locale)}

    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found in local database")

    search_result = search_vocadb(
        track.producer.split(",")[0].strip(), track.title, track.title_jp
    )
    song_id = search_result.get("song_id")

    if not song_id:
        return {"lyrics": []}

    return get_vocadb_lyrics(song_id, track_id=track_id, db=db, locale=locale)


@router.get("/api/vocadb_artist_search")
def search_vocadb_artist(producer: str):
    url = vocadb.search_artist(producer)
    if url:
        return {"url": url}
    return {"url": None}


@router.get("/api/vocadb_search")
def search_vocadb(producer: str, title_en: str, title_jp: str | None = None):
    return vocadb.search_song(producer, title_en, title_jp)


@router.get("/api/vocadb_lyrics/{song_id}")
def get_vocadb_lyrics(
    song_id: int,
    track_id: Optional[int] = None,
    db: Session = Depends(get_db),
    locale: str = Depends(get_locale),
):
    if track_id:
        cached_lyrics = (
            db.query(models.Lyric).filter(models.Lyric.track_id == track_id).all()
        )
        if cached_lyrics:
            logging.info("Serving cached lyrics for track %s", track_id)
            return {"lyrics": _format_cached_lyrics(cached_lyrics, locale)}

    available_lyrics = vocadb.fetch_lyrics(song_id)
    if not available_lyrics:
        return {"lyrics": []}

    if track_id:
        for lyric_obj in available_lyrics:
            new_lyric = models.Lyric(
                track_id=track_id,
                language=lyric_obj["language"],
                translation_type=lyric_obj["translation_type"],
                source=lyric_obj["source"],
                url=lyric_obj["url"],
                content=lyric_obj["text"],
            )
            db.add(new_lyric)
        db.commit()
        logging.info("Cached %s lyrics for track %s", len(available_lyrics), track_id)

    def sort_key(lyric: dict[str, str]) -> int:
        if locale == "ja":
            if "Japanese" in lyric["label"]:
                return 0
            if "Romaji" in lyric["label"]:
                return 1
            if "English" in lyric["label"]:
                return 2
        else:
            if "English" in lyric["label"]:
                return 0
            if "Romaji" in lyric["label"]:
                return 1
            if "Japanese" in lyric["label"]:
                return 2
        return 3

    available_lyrics.sort(key=sort_key)
    return {"lyrics": available_lyrics}
