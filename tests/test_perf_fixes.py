"""Tests for performance fixes (Phase 3).

Each test maps to a specific fix so regressions are caught at the right layer.
"""

from app.constants import MAX_UNAUTHENTICATED_LIMIT
from app.utils.view_helpers import build_limit_offset, limit_ceiling

# --- Fix 2: cap limit=all for unauthenticated requests -----------------------


def test_build_limit_offset_clamps_all_for_anonymous():
    total = 10_000
    limit_val, total_pages, skip = build_limit_offset(
        "all", total, page=1, ceiling=MAX_UNAUTHENTICATED_LIMIT
    )
    assert limit_val == MAX_UNAUTHENTICATED_LIMIT
    assert skip == 0
    assert total_pages == (total + limit_val - 1) // limit_val


def test_build_limit_offset_all_unlimited_for_authenticated():
    total = 10_000
    limit_val, _, _ = build_limit_offset("all", total, page=1, ceiling=None)
    assert limit_val == total


def test_build_limit_offset_clamps_oversized_numeric_limit():
    limit_val, _, _ = build_limit_offset(
        "9999", 10_000, page=1, ceiling=MAX_UNAUTHENTICATED_LIMIT
    )
    assert limit_val == MAX_UNAUTHENTICATED_LIMIT


def test_limit_ceiling_none_for_user_capped_for_anonymous():
    assert limit_ceiling(None) == MAX_UNAUTHENTICATED_LIMIT
    assert limit_ceiling(object()) is None


def test_get_tracks_partial_defaults_to_100(client_factory, sample_tracks):
    client = client_factory()
    response = client.get("/_/get_tracks")
    assert response.status_code == 200
    assert response.json()["pagination"]["limit"] == "100"


# --- Fix 3: memoize translations per locale -----------------------------------


def test_translations_are_memoized_per_locale():
    from app.dependencies import _load_translations, get_translations

    _load_translations.cache_clear()
    first = get_translations("en")
    second = get_translations("en")
    assert first is second
    assert _load_translations.cache_info().hits >= 1
