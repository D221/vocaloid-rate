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


# --- Fix 4: cache-control policy ----------------------------------------------


def test_robots_is_publicly_cacheable(client_factory):
    client = client_factory()
    response = client.get("/robots.txt")
    cache = response.headers["cache-control"]
    assert cache.startswith("public")
    assert "s-maxage=" in cache
    assert "stale-while-revalidate=" in response.headers["cache-control"]
    assert "cookie" in response.headers.get("vary", "").lower()


def test_snapshot_is_publicly_cacheable_for_anonymous(client_factory, sample_tracks):
    client = client_factory()
    response = client.get("/api/playlist-snapshot")
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("public")


def test_personalised_request_is_private_no_store(client_factory, sample_tracks):
    client = client_factory()
    # A session cookie marks the response as personalised even on a public path.
    response = client.get(
        "/api/playlist-snapshot", cookies={"access_token": "session-token"}
    )
    assert response.headers["cache-control"] == "private, no-store"


# --- Fix 5: atproto is not imported on cold start -----------------------------


def test_atproto_not_imported_on_cold_start():
    import os
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(project_root)
    code = "import sys; import app.main; print('atproto' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(project_root),
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


# --- Fix 6: producer/voicebank pages cap rendered tracks ----------------------


def test_producer_page_caps_rendered_tracks(client_factory, db_session):
    from datetime import datetime, timezone

    from app import models
    from app.constants import ENTITY_PAGE_LIMIT

    producer = models.Producer(name="Prolific", name_jp="P")
    db_session.add(producer)
    db_session.flush()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    total = ENTITY_PAGE_LIMIT + 5
    for i in range(total):
        track = models.Track(
            title=f"T{i}",
            producer="Prolific",
            voicebank="V",
            published_date=now,
            link=f"https://x/{i}",
            rank=None,
        )
        db_session.add(track)
        db_session.flush()
        track.producers.append(producer)
    db_session.commit()

    client = client_factory()
    response = client.get("/producer/Prolific")
    assert response.status_code == 200
    rendered = response.text.count("truncate font-bold text-cyan-text")
    assert rendered == ENTITY_PAGE_LIMIT


# --- Fix 7: bot guard rejects absurd query params -----------------------------


def test_absurd_limit_is_rejected(client_factory, sample_tracks):
    client = client_factory()
    assert client.get("/_/get_tracks?limit=abc").status_code == 400
    assert client.get("/?page=notanumber").status_code == 400
    assert client.get("/?page=99999999").status_code == 400


def test_valid_limit_all_is_allowed(client_factory, sample_tracks):
    client = client_factory()
    assert client.get("/?limit=all").status_code == 200


def test_robots_disallows_heavy_paths(client_factory):
    client = client_factory()
    body = client.get("/robots.txt").text
    assert "Disallow: /_/" in body
    assert "Disallow: /api/" in body
    assert "Disallow: /*?limit=all" in body
