import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

logger = logging.getLogger(__name__)

BASE_URL_EN = "https://vocaloard.injpok.tokyo/en/"
BASE_URL_JP = "https://vocaloard.injpok.tokyo/"


def _fetch_page(url: str) -> requests.Response:
    """Helper to fetch a URL with requests."""
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response


# This is the new helper function that scrapes just ONE page.
def _scrape_single_page(page_num: int) -> list[dict]:
    """Scrapes a single page of the ranking and returns a list of track dictionaries."""
    tracks_on_page = []
    url_en = f"{BASE_URL_EN}?g={page_num}"
    url_jp = f"{BASE_URL_JP}?g={page_num}"

    logger.info(f"Fetching page {page_num} in parallel.")
    try:
        # Fetch English and Japanese versions in parallel to save time
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_en = executor.submit(_fetch_page, url_en)
            future_jp = executor.submit(_fetch_page, url_jp)
            response_en = future_en.result()
            response_jp = future_jp.result()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data for page {page_num}: {e}")
        return []

    soup_en = BeautifulSoup(response_en.content, "html.parser")
    soup_jp = BeautifulSoup(response_jp.content, "html.parser")

    rows_en = soup_en.select("div.RankingItem.area")
    rows_jp = soup_jp.select("div.RankingItem.area")

    for row_en, row_jp in zip(rows_en, rows_jp):
        try:
            link_tag = row_en.find("a")
            if not isinstance(link_tag, Tag):
                continue
            link = link_tag.get("href")
            if not link:
                continue

            title_tag = row_en.select_one(".song-title")
            producer_tag = row_en.select_one(".artists")
            voicebank_tag = row_en.select_one(".singers")
            published_tag = row_en.select_one(".published")
            image_tag = row_en.select_one(".image-area img")
            rank_tag = row_en.select_one(".rank-p")

            # Robust checks and type narrowing
            if (
                not isinstance(title_tag, Tag)
                or not isinstance(producer_tag, Tag)
                or not isinstance(voicebank_tag, Tag)
                or not isinstance(published_tag, Tag)
                or not isinstance(image_tag, Tag)
                or not isinstance(rank_tag, Tag)
            ):
                logger.warning(
                    f"Skipping row on page {page_num} due to missing elements."
                )
                continue

            image_url = image_tag.get("src")
            if not isinstance(image_url, str):
                continue

            title_jp_tag = row_jp.select_one(".song-title")
            producer_jp_tag = row_jp.select_one(".artists")
            voicebank_jp_tag = row_jp.select_one(".singers")

            track_data = {
                "title": title_tag.text.strip(),
                "title_jp": title_jp_tag.text.strip()
                if title_jp_tag and title_jp_tag.text.strip() != title_tag.text.strip()
                else None,
                "link": link,
                "producer": producer_tag.text.strip(),
                "producer_jp": producer_jp_tag.text.strip()
                if producer_jp_tag
                and producer_jp_tag.text.strip() != producer_tag.text.strip()
                else None,
                "voicebank": voicebank_tag.text.strip(),
                "voicebank_jp": voicebank_jp_tag.text.strip()
                if voicebank_jp_tag
                and voicebank_jp_tag.text.strip() != voicebank_tag.text.strip()
                else None,
                "published_date": datetime.datetime.strptime(
                    published_tag.text.strip(), "%Y/%m/%d"
                ),
                "image_url": image_url,
                "rank": int(rank_tag.text.strip()),
            }
            tracks_on_page.append(track_data)
        except (ValueError, TypeError) as e:
            logger.error(f"Error converting data for a row on page {page_num}: {e}")
        except Exception as e:
            logger.error(
                f"An unexpected error occurred parsing a row on page {page_num}: {e}",
                exc_info=True,
            )

    return tracks_on_page
