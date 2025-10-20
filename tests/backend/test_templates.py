"""Tests for listing templates rendering."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.listing_fields import ListingFields
from app.backend.templates import ListingTemplateRegistry


def test_render_defaults_to_femme_when_gender_missing_levis() -> None:
    template = ListingTemplateRegistry().get_template("template-jean-levis-femme")
    fields = ListingFields(
        model="501",
        fr_size="38",
        us_w="28",
        us_l="30",
        fit_leg="slim",
        rise_class="haute",
        rise_measurement_cm=None,
        cotton_pct="99",
        polyester_pct="",
        elastane_pct="1",
        gender="",
        color_main="bleu",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="JLF1",
    )

    title, description = template.render(fields)

    assert "femme" in title.lower()
    assert "femme" in description.lower()
    assert "#levisfemme" in description.lower()
