import os
from pathlib import Path

from app.config import get_data_dir, is_vercel

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SUPPORTED_LOCALES = ["en", "ja"]
DEFAULT_LOCALE = "en"
DATA_DIR = str(get_data_dir())
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MiB
VALID_PAGE_LIMITS = {"all", "25", "50", "100"}
# Upper bound on rows returned for a single unauthenticated request. "all" is
# clamped to this for anonymous callers so a crawler cannot force a full-catalog
# render (which is ~20x the CPU of a 100-row page). Authenticated users may
# still request the full set.
MAX_UNAUTHENTICATED_LIMIT = 500
# Cap on tracks rendered on producer/voicebank entity pages. These pages are
# public and listed in the sitemap, so an unbounded track list is a crawler
# amplifier; the full catalog remains reachable via the paginated main chart.
ENTITY_PAGE_LIMIT = 200

if is_vercel():
    SCRAPE_STATUS_FILE = os.path.join("/tmp", "scrape_status.txt")
else:
    SCRAPE_STATUS_FILE = os.path.join(DATA_DIR, "scrape_status.txt")

RESOURCE_BASE_PATH: Path | None = None


def set_resource_base_path(path: Path) -> None:
    global RESOURCE_BASE_PATH
    RESOURCE_BASE_PATH = path


def get_resource_base_path() -> Path:
    if RESOURCE_BASE_PATH is not None:
        return RESOURCE_BASE_PATH
    return BASE_DIR.parent
