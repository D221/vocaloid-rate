"""Regression tests for static asset weight.

Every byte here is paid on cold page loads site-wide (favicons are
requested by browsers on essentially every visit), so oversized
assets get a hard budget.
"""

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "app" / "static"

# A multi-resolution .ico (16/32/48px, PNG-compressed) is ~5-15KB.
# The previous 285KB build cost more than all JS combined on cold loads.
FAVICON_BUDGET_BYTES = 32 * 1024


def test_favicon_ico_stays_small():
    size = (STATIC_DIR / "favicon.ico").stat().st_size

    assert size < FAVICON_BUDGET_BYTES, (
        f"favicon.ico is {size} bytes (budget {FAVICON_BUDGET_BYTES}); "
        "regenerate it from a PNG source instead of committing a BMP bundle"
    )
