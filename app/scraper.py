import datetime
import logging

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

logger = logging.getLogger(__name__)

BASE_URL_EN = "https://vocaloard.injpok.tokyo/en/"
BASE_URL_JP = "https://vocaloard.injpok.tokyo/"


# This is the new helper function that scrapes just ONE page.
def _scrape_single_page(page_num: int):
    """Scrapes a single page of the ranking and returns a list of track dictionaries."""
    tracks_on_page = []
    url_en = f"{BASE_URL_EN}?g={page_num}"
    url_jp = f"{BASE_URL_JP}?g={page_num}"

    logger.info(f"Fetching page {page_num}: {url_en}")
    try:
        response_en = requests.get(url_en, timeout=15)
        response_jp = requests.get(url_jp, timeout=15)
        response_en.raise_for_status()
        response_jp.raise_for_status()
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

            if not all(
                [
                    title_tag,
                    producer_tag,
                    voicebank_tag,
                    published_tag,
                    image_tag,
                    rank_tag,
                ]
            ):
                continue

            assert (
                title_tag
                and producer_tag
                and voicebank_tag
                and published_tag
                and image_tag
                and rank_tag
            )

            image_url = image_tag.get("src")
            if not image_url:
                continue

            title_jp_tag = row_jp.select_one(".song-title")

            track_data = {
                "title": title_tag.text.strip(),
                "title_jp": title_jp_tag.text.strip()
                if title_jp_tag and title_jp_tag.text.strip() != title_tag.text.strip()
                else None,
                "link": link,
                "producer": producer_tag.text.strip(),
                "voicebank": voicebank_tag.text.strip(),
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


# This is the new main function that calls the helper.
def scrape_all_pages():
    """Scrapes all pages of the ranking by calling _scrape_single_page in a loop."""
    all_tracks = []
    for page in range(1, 7):
        all_tracks.extend(_scrape_single_page(page))
    logger.info(f"Scraper finished. Total tracks collected: {len(all_tracks)}")
    return all_tracks
