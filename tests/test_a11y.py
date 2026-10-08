"""Accessibility regression tests for form control names.

Screen readers need an accessible name for every control. These tests
render the real pages and assert the controls expose one.
"""

import re


def _tags(html: str, pattern: str) -> list[str]:
    return re.findall(pattern, html)


def test_star_rating_inputs_have_accessible_names(client_factory, user, sample_tracks):
    client = client_factory(optional_user=user)

    response = client.get("/")

    assert response.status_code == 200
    radios = _tags(response.text, r"<input[^>]*name=\"rating\"[^>]*>")
    assert radios, "expected star rating inputs on the homepage"
    unnamed = [tag for tag in radios if "aria-label=" not in tag]
    assert unnamed == []


def test_notes_textarea_has_accessible_name(client_factory, sample_tracks):
    client = client_factory()

    response = client.get("/")

    assert response.status_code == 200
    areas = _tags(response.text, r"<textarea[^>]*data-notes-input[^>]*>")
    assert areas, "expected notes textareas on the homepage"
    assert all("aria-label=" in tag for tag in areas)


def test_lyrics_language_select_has_accessible_name(client_factory, sample_tracks):
    client = client_factory()

    response = client.get("/")

    assert response.status_code == 200
    selects = _tags(response.text, r"<select[^>]*data-lyrics-select[^>]*>")
    assert selects, "expected lyrics language selects on the homepage"
    assert all("aria-label=" in tag for tag in selects)


def test_filter_search_inputs_have_accessible_names(client_factory, sample_tracks):
    client = client_factory()

    response = client.get("/")

    assert response.status_code == 200
    for field in ("title_filter", "producer_filter", "voicebank_filter"):
        tags = _tags(response.text, rf"<input[^>]*name=\"{field}\"[^>]*>")
        assert tags, f"expected {field} input on the homepage"
        assert all("aria-label=" in tag for tag in tags), field


def test_music_player_sliders_have_accessible_names(client_factory):
    client = client_factory()

    response = client.get("/about")

    assert response.status_code == 200
    sliders = _tags(response.text, r"<input[^>]*type=\"range\"[^>]*>")
    assert sliders, "expected music player sliders in base layout"
    assert all(("aria-label=" in tag or "title=" in tag) for tag in sliders)
