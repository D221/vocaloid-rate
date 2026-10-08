"""Regression tests for Subresource Integrity (SRI) hashes on CDN scripts.

A wrong integrity hash silently blocks the script in browsers, which broke
htmx's json-enc extension (and with it the registration form in
register.html, which posts JSON via hx-ext="json-enc"). These pins were
verified against real browser loads: a mismatched hash always surfaces as a
console error and the script never executes.
"""

import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"

# Verified against the bytes served by
# https://unpkg.com/htmx-ext-json-enc@2.0.1 (pinned version, immutable).
HTMX_JSON_ENC_SRC = "https://unpkg.com/htmx-ext-json-enc@2.0.1"
HTMX_JSON_ENC_SRI = (
    "sha384-fU2gwx20YcGXySGydrPaoJC4ea0NrbR57aVtU79A0lmU41xUEo5d1Z99US+p4ox2"
)

HTMX_SRC = "https://unpkg.com/htmx.org@2.0.4"
HTMX_SRI = "sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+"

CHART_JS_SRC = "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"
CHART_JS_SRI = "sha384-vsrfeLOOY6KuIYKDlmVH5UiBmgIdB1oEf7p01YgWHuqmOHfZr374+odEv96n9tNC"


def _script_tag_for(template: str, src: str) -> str:
    text = (TEMPLATES_DIR / template).read_text(encoding="utf-8")
    match = re.search(
        r"<script[^>]*src=[\"']" + re.escape(src) + r"[\"'][^>]*>",
        text,
    )
    assert match is not None, f"no script tag for {src} in {template}"
    return match.group(0)


def _assert_sri(template: str, src: str, expected: str) -> None:
    tag = _script_tag_for(template, src)
    integrity = re.search(r'integrity="([^"]+)"', tag)
    assert integrity is not None, f"{src} in {template} has no integrity hash"
    assert integrity.group(1) == expected


def test_htmx_json_enc_script_tag_ships_valid_sri_hash():
    _assert_sri("base.html", HTMX_JSON_ENC_SRC, HTMX_JSON_ENC_SRI)


def test_htmx_core_script_tag_ships_valid_sri_hash():
    _assert_sri("base.html", HTMX_SRC, HTMX_SRI)


def test_chart_js_script_tag_ships_valid_sri_hash_in_rated():
    _assert_sri("rated.html", CHART_JS_SRC, CHART_JS_SRI)


def test_chart_js_script_tag_ships_valid_sri_hash_in_user_profile():
    _assert_sri("user_profile.html", CHART_JS_SRC, CHART_JS_SRI)
