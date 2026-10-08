"""Regression tests for frontend default settings shipped in JS sources.

The homepage default page size must stay in sync with the server-side
fallback in read_root (pages.py): first-time visitors with no saved
preference should get a paginated list, not the full track table.
"""

import re
from pathlib import Path

OPTIONS_JS = (
    Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "options.js"
)


def test_options_page_defaults_page_size_to_paginated_limit():
    text = OPTIONS_JS.read_text(encoding="utf-8")
    match = re.search(
        r'localStorage\.getItem\("defaultPageSize"\)\s*\|\|\s*"([^"]+)"',
        text,
    )
    assert match is not None, "defaultPageSize fallback not found in options.js"
    assert match.group(1) == "100"


def test_track_list_browser_url_default_page_size_matches_server():
    main_js = (
        Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "main.js"
    )
    text = main_js.read_text(encoding="utf-8")
    fallbacks = re.findall(
        r'localStorage\.getItem\("defaultPageSize"\)\s*\|\|\s*"([^"]+)"',
        text,
    )
    assert fallbacks, "no defaultPageSize fallback found in main.js"
    assert fallbacks == ["100"] * len(fallbacks)
