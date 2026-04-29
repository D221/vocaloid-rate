import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

VOCADB_API_BASE = "https://vocadb.net/api"
VOCADB_BASE = "https://vocadb.net"


def search_artist(producer: str) -> Optional[str]:
    """Searches for an artist on VocaDB and returns their URL."""
    headers = {"Accept": "application/json"}
    try:
        url = f"{VOCADB_API_BASE}/artists?query={quote(producer)}&maxResults=1&sort=FollowerCount"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("items"):
            artist_id = data["items"][0]["id"]
            # Artist URLs on VocaDB use the /Ar/ prefix
            return f"{VOCADB_BASE}/Ar/{artist_id}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling VocaDB Artist API: {e}", exc_info=True)
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during VocaDB artist search: {e}",
            exc_info=True,
        )
    return None


def search_song(
    producer: str, title_en: str, title_jp: Optional[str] = None
) -> Dict[str, Any]:
    """Searches for a song on VocaDB and returns its URL and ID."""
    headers = {"Accept": "application/json"}
    try:
        # Step 1: Find the Artist ID
        artist_search_url = f"{VOCADB_API_BASE}/artists?query={quote(producer)}&maxResults=1&sort=FollowerCount"
        artist_response = requests.get(artist_search_url, headers=headers, timeout=10)
        artist_response.raise_for_status()
        artist_data = artist_response.json()

        if not artist_data.get("items"):
            return {"url": None, "song_id": None}
        artist_id = artist_data["items"][0]["id"]

        # Step 2: Search with English title first
        song_search_url = f"{VOCADB_API_BASE}/songs?query={quote(title_en)}&songTypes=Original&artistId[]={artist_id}&maxResults=1&sort=RatingScore"
        song_response = requests.get(song_search_url, headers=headers, timeout=10)
        song_response.raise_for_status()
        song_data = song_response.json()

        # If English search fails AND we have a Japanese title, try it as a fallback
        if not song_data.get("items") and title_jp:
            logger.info(
                f"VocaDB: English search failed for '{title_en}'. Trying Japanese title '{title_jp}'."
            )
            song_search_url = f"{VOCADB_API_BASE}/songs?query={quote(title_jp)}&songTypes=Original&artistId[]={artist_id}&maxResults=1&sort=RatingScore"
            song_response = requests.get(song_search_url, headers=headers, timeout=10)
            song_response.raise_for_status()
            song_data = song_response.json()

        if song_data.get("items"):
            song = song_data["items"][0]
            song_id = song["id"]
            song_url = f"{VOCADB_BASE}/S/{song_id}"
            return {"url": song_url, "song_id": song_id}

    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling VocaDB API: {e}", exc_info=True)
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during VocaDB search: {e}", exc_info=True
        )

    return {"url": None, "song_id": None}


def fetch_lyrics(song_id: int) -> List[Dict[str, Any]]:
    """Fetches and normalizes lyrics for a song from VocaDB."""
    headers = {"Accept": "application/json"}
    try:
        api_url = f"{VOCADB_API_BASE}/songs/{song_id}?fields=Lyrics"
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        lyrics_list = data.get("lyrics", [])
        if not lyrics_list:
            return []

        normalized_lyrics = []
        for lyric_data in lyrics_list:
            text = lyric_data.get("value", "").replace("\n", "<br>")
            culture_codes = lyric_data.get("cultureCodes", [])
            lang_code = culture_codes[0] if culture_codes else ""
            trans_type = lyric_data.get("translationType", "Unknown")

            # Map culture code to readable language name
            lang_name = "Unknown"
            if "ja" in lang_code:
                lang_name = "Japanese"
            elif "en" in lang_code:
                lang_name = "English"
            elif lang_code == "":
                lang_name = "Romaji" if trans_type == "Romanized" else "Other"

            lyric_obj = {
                "label": f"{lang_name} - {trans_type}",
                "text": text,
                "source": lyric_data.get("source", "VocaDB"),
                "url": lyric_data.get("url", ""),
                "translation_type": trans_type,
                "language": lang_name,
            }

            # Pre-save cleanup for specific labels
            if trans_type == "Romanized":
                lyric_obj["label"] = "Romaji"
            elif trans_type == "Translation" and lang_name == "English":
                lyric_obj["label"] = "English (Translation)"
            elif trans_type == "Original" and lang_name == "Japanese":
                lyric_obj["label"] = "Japanese (Original)"

            normalized_lyrics.append(lyric_obj)

        return normalized_lyrics

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching lyrics from VocaDB API: {e}", exc_info=True)
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during lyrics fetch: {e}", exc_info=True
        )

    return []
