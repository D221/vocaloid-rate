import datetime
import logging

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

logger = logging.getLogger(__name__)

BASE_URL_EN = "https://vocaloard.injpok.tokyo/en/"
BASE_URL_JP = "https://vocaloard.injpok.tokyo/"


def scrape_tracks():
    tracks = []
    for page in range(1, 7):
        url_en = f"{BASE_URL_EN}?g={page}"
        url_jp = f"{BASE_URL_JP}?g={page}"

        logger.info(f"Scraping page {page}: {url_en}")

        try:
            response_en = requests.get(url_en, timeout=15)
            response_jp = requests.get(url_jp, timeout=15)
            response_en.raise_for_status()
            response_jp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data for page {page}: {e}")
            continue

        soup_en = BeautifulSoup(response_en.content, "html.parser")
        soup_jp = BeautifulSoup(response_jp.content, "html.parser")

        rows_en = soup_en.select("div.RankingItem.area")
        rows_jp = soup_jp.select("div.RankingItem.area")

        logger.info(f"Found {len(rows_en)} tracks on page {page}")

        for row_en, row_jp in zip(rows_en, rows_jp):
            try:
                link_tag = row_en.find("a")
                if not isinstance(link_tag, Tag):
                    logger.warning(
                        f"Skipping a row on page {page}: Could not find a valid link tag."
                    )
                    continue

                link = link_tag.get("href")
                if not link:
                    logger.warning(
                        f"Skipping a row on page {page}: Link tag found, but has no 'href'."
                    )
                    continue

                title_tag = row_en.select_one(".song-title")
                producer_tag = row_en.select_one(".artists")
                voicebank_tag = row_en.select_one(".singers")
                published_tag = row_en.select_one(".published")
                image_tag = row_en.select_one(".image-area img")
                rank_tag = row_en.select_one(".rank-p")

                # This check is still great for catching the error at runtime.
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
                    logger.warning(
                        f"Skipping a row for track '{link}': Missing one or more essential data tags."
                    )
                    continue

                assert title_tag is not None
                assert producer_tag is not None
                assert voicebank_tag is not None
                assert published_tag is not None
                assert image_tag is not None
                assert rank_tag is not None

                title_en = title_tag.text.strip()
                producer = producer_tag.text.strip()
                voicebank = voicebank_tag.text.strip()
                published_date_str = published_tag.text.strip()
                image_url = image_tag.get("src")
                rank_text = rank_tag.text.strip()

                if not image_url:
                    logger.warning(
                        f"Image tag for '{title_en}' is missing 'src', skipping."
                    )
                    continue

                title_jp_tag = row_jp.select_one(".song-title")
                title_jp = title_jp_tag.text.strip() if title_jp_tag else None

                published_date = datetime.datetime.strptime(
                    published_date_str, "%Y/%m/%d"
                )
                rank = int(rank_text)

                if title_en == title_jp:
                    title_jp = None

                track = {
                    "title": title_en,
                    "title_jp": title_jp,
                    "link": link,
                    "producer": producer,
                    "voicebank": voicebank,
                    "published_date": published_date,
                    "image_url": image_url,
                    "rank": rank,
                }
                tracks.append(track)

            except (ValueError, TypeError) as e:
                logger.error(f"Error converting data for a row on page {page}: {e}")
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred parsing a row on page {page}: {e}",
                    exc_info=True,
                )

    logger.info(f"Scraper finished. Total tracks collected: {len(tracks)}")
    return tracks
