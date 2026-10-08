"""Regression tests for entity grid layouts (producers, voicebanks, profiles).

Grid children default to min-width:auto, so one long unbreakable entity
name forces its column track wider than the viewport and the whole page
overflows horizontally. The cards must be allowed to shrink (min-w-0)
with names wrapping (break-words).
"""

import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"

ENTITY_GRIDS = ["entity_index.html", "profiles_index.html"]


def test_entity_grid_cards_can_shrink_with_wrapping_names():
    for template in ENTITY_GRIDS:
        text = (TEMPLATES_DIR / template).read_text(encoding="utf-8")
        cards = re.findall(r"<a[^>]*class=\"([^\"]*)\"", text)
        assert cards, f"no card anchors found in {template}"
        for classes in cards:
            assert "min-w-0" in classes.split(), (
                f"entity card in {template} must have min-w-0 to avoid "
                "horizontal page overflow"
            )
        headings = re.findall(r"<h2[^>]*class=\"([^\"]*)\"", text)
        assert headings, f"no card headings found in {template}"
        for classes in headings:
            assert "break-words" in classes.split(), (
                f"entity card heading in {template} must wrap long names"
            )
