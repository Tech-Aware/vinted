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


def test_render_pull_tommy_femme_updates_hashtag_with_size() -> None:
    template = ListingTemplateRegistry().get_template("template-pull-tommy-femme")

    fields = ListingFields(
        model="",
        fr_size="XL",
        us_w="",
        us_l="",
        fit_leg="",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="",
        polyester_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="",
        defects="",
        defect_tags=(),
        size_label_visible=False,
        fabric_label_visible=False,
        sku="PTF42",
    )

    _, description = template.render(fields)

    paragraphs = description.split("\n\n")
    assert any("#durin31tfXL" in line for line in paragraphs[3].splitlines())

    hashtags_line = paragraphs[-1]
    hashtags = [token for token in hashtags_line.split() if token.startswith("#")]
    assert "#durin31tfXL" in hashtags


def test_render_pull_tommy_femme_marketing_highlight_varies_with_materials() -> None:
    template = ListingTemplateRegistry().get_template("template-pull-tommy-femme")

    cotton_fields = ListingFields(
        model="",
        fr_size="M",
        us_w="",
        us_l="",
        fit_leg="",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="95",
        polyester_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="bleu",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="",
    )

    cashmere_fields = ListingFields(
        model="",
        fr_size="M",
        us_w="",
        us_l="",
        fit_leg="",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="60",
        wool_pct="",
        cashmere_pct="15",
        polyester_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="beige",
        knit_pattern="torsadé",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="",
    )

    _, cotton_description = template.render(cotton_fields)
    _, cashmere_description = template.render(cashmere_fields)

    cotton_highlight = cotton_description.split("\n\n")[1].splitlines()[0]
    cashmere_highlight = cashmere_description.split("\n\n")[1].splitlines()[0]

    assert cotton_highlight != cashmere_highlight
    assert "respir" in cotton_highlight.lower()
    assert "cachemire" in cashmere_highlight.lower()


def test_render_pull_tommy_femme_title_avoids_pattern_duplicates() -> None:
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
        cotton_pct="40",
        polyester_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="marron",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="PTF1",
        wool_pct="60",
        knit_pattern="torsadé",
        made_in="Made in Portugal",
    )

    title, _ = template.render(fields)

    assert title == "Pull Tommy femme taille M en laine torsadée marron Made in Europe - PTF1"
    assert title.lower().count("torsad") == 1
