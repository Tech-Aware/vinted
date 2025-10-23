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
        waist_measurement_cm=None,
        cotton_pct="99",
        polyester_pct="",
        viscose_pct="",
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


def test_render_pull_tommy_femme_includes_made_in_europe_and_hashtags() -> None:
    template = ListingTemplateRegistry().get_template("template-pull-tommy-femme")
    fields = ListingFields(
        model="",
        fr_size="M",
        us_w="",
        us_l="",
        fit_leg="",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="100",
        polyester_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="blanc et noir",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="PTF01",
        knit_pattern="marinière",
        made_in="Made in Portugal",
    )

    title, description = template.render(fields)

    assert "Pull Tommy femme" in title
    assert "100% coton" in title
    assert "blanc et noir marinière" in title
    assert "Made in Europe" in title
    assert title.endswith("PTF01")

    assert "Tommy Hilfiger" in description
    assert "Fabriqué en Europe" in description
    assert "Made in Portugal" in description
    assert "Mesures détaillées visibles en photo" in description

    hashtags_line = description.splitlines()[-1]
    hashtags = [token for token in hashtags_line.split() if token.startswith("#")]
    assert "#durin31tfM" in hashtags
    assert len(hashtags) == len(set(hashtags))
    assert len(hashtags) >= 10
