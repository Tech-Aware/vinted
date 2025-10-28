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
        polyamide_pct="",
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


def test_render_jean_levis_femme_uses_sku_placeholder_when_missing() -> None:
    template = ListingTemplateRegistry().get_template("template-jean-levis-femme")
    fields = ListingFields(
        model="501",
        fr_size="38",
        us_w="",
        us_l="",
        fit_leg="straight",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="98",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="Femme",
        color_main="bleu",
        defects="",
        defect_tags=(),
        size_label_visible=False,
        fabric_label_visible=False,
        sku="",
    )

    title, description = template.render(fields)

    assert title.endswith("SKU/nc")
    assert "sku" not in description.lower()


def test_render_jean_levis_handles_fabric_label_cut() -> None:
    template = ListingTemplateRegistry().get_template("template-jean-levis-femme")
    fields = ListingFields(
        model="505",
        fr_size="40",
        us_w="30",
        us_l="32",
        fit_leg="straight",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="Femme",
        color_main="bleu",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=False,
        fabric_label_cut=True,
        sku="JLF20",
    )

    _, description = template.render(fields)

    assert description.count("Étiquette matière coupée pour plus de confort.") == 1


def test_render_jean_levis_avoids_duplicate_missing_fabric_label_sentence() -> None:
    template = ListingTemplateRegistry().get_template("template-jean-levis-femme")
    fields = ListingFields(
        model="",
        fr_size="",
        us_w="",
        us_l="",
        fit_leg="",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="",
        defects="",
        defect_tags=(),
        size_label_visible=False,
        fabric_label_visible=False,
        fabric_label_cut=False,
        sku="JLF21",
    )

    _, description = template.render(fields)

    assert description.count("Étiquettes coupées pour plus de confort.") == 1
    assert description.count("Étiquette taille non visible sur les photos.") == 1


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
        polyamide_pct="",
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

    assert "Pull Tommy Hilfiger femme" in title
    assert "100% coton" in title
    assert "blanc et noir marinière" in title
    assert "Made in Europe" in title
    assert title.endswith("PTF01")

    assert "Tommy Hilfiger" in description
    assert "Fabriqué en Europe" in description
    assert "Made in Portugal" in description
    assert "Mesures détaillées visibles en photo" in description
    assert "Référence SKU" not in description

    hashtags_line = description.splitlines()[-1]
    hashtags = [token for token in hashtags_line.split() if token.startswith("#")]
    assert "#durin31tfM" in hashtags
    assert len(hashtags) == len(set(hashtags))
    assert len(hashtags) >= 10


def test_render_pull_tommy_femme_handles_fabric_label_cut() -> None:
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
        cotton_pct="",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="bleu",
        defects="",
        defect_tags=(),
        size_label_visible=False,
        fabric_label_visible=False,
        fabric_label_cut=True,
        sku="PTF99",
    )

    _, description = template.render(fields)

    assert description.count("Étiquette matière coupée pour plus de confort.") == 1
    assert "Référence SKU" not in description


def test_render_pull_tommy_femme_handles_hidden_fabric_label() -> None:
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
        cotton_pct="",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="bleu",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=False,
        fabric_label_cut=False,
        sku="PTF98",
    )

    _, description = template.render(fields)

    assert description.count("Étiquettes coupées pour plus de confort.") == 1
    assert "Étiquette composition non visible sur les photos." not in description
    assert "Référence SKU" not in description


def test_render_jean_levis_includes_polyamide_when_present() -> None:
    template = ListingTemplateRegistry().get_template("template-jean-levis-femme")
    fields = ListingFields(
        model="721",
        fr_size="38",
        us_w="28",
        us_l="30",
        fit_leg="slim",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="70",
        polyester_pct="",
        polyamide_pct="12",
        viscose_pct="",
        elastane_pct="2",
        gender="Femme",
        color_main="bleu",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="JLF9",
    )

    _, description = template.render(fields)

    assert "12% polyamide" in description


def test_render_pull_tommy_femme_switches_to_cardigan() -> None:
    template = ListingTemplateRegistry().get_template("template-pull-tommy-femme")

    fields = ListingFields(
        model="",
        fr_size="S",
        us_w="",
        us_l="",
        fit_leg="",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="80",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="beige",
        knit_pattern="torsadé",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="PTF55",
        is_cardigan=True,
    )

    title, description = template.render(fields)

    assert title.startswith("Gilet Tommy Hilfiger femme")
    assert description.splitlines()[0].startswith("Gilet Tommy Hilfiger")
    hashtags_line = description.splitlines()[-1]
    assert "#gilettommy" in hashtags_line
    assert "#pulltommy" not in hashtags_line


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
        polyamide_pct="",
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


def test_render_pull_tommy_femme_normalizes_extended_sizes() -> None:
    template = ListingTemplateRegistry().get_template("template-pull-tommy-femme")

    fields = ListingFields(
        model="",
        fr_size="1X",
        us_w="",
        us_l="",
        fit_leg="",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="marine",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=False,
        sku="PTF07",
    )

    title, description = template.render(fields)

    assert "taille XL" in title
    assert "1X" not in title

    first_sentence = description.splitlines()[0]
    assert "taille XL." in first_sentence
    assert "1X" not in description

    hashtags_line = description.splitlines()[-1]
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
        polyamide_pct="",
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
        polyamide_pct="",
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

    pure_cotton_fields = ListingFields(
        model="",
        fr_size="S",
        us_w="",
        us_l="",
        fit_leg="",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="100",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="blanc",
        knit_pattern="rayé",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="",
    )

    _, cotton_description = template.render(cotton_fields)
    _, cashmere_description = template.render(cashmere_fields)
    _, pure_cotton_description = template.render(pure_cotton_fields)

    cotton_highlight = cotton_description.split("\n\n")[1].splitlines()[0]
    cashmere_highlight = cashmere_description.split("\n\n")[1].splitlines()[0]
    pure_cotton_highlight = pure_cotton_description.split("\n\n")[1].splitlines()[0]

    assert cotton_highlight != cashmere_highlight
    assert "respir" in cotton_highlight.lower()
    assert "cachemire" in cashmere_highlight.lower()
    assert pure_cotton_highlight.startswith("Maille 100% coton")


def test_render_pull_tommy_femme_uses_sku_placeholder_when_missing() -> None:
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
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="rouge",
        knit_pattern="marinière",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="",
    )

    title, description = template.render(fields)

    assert title.endswith("SKU/nc")
    assert "Référence SKU" not in description


def test_render_pull_tommy_femme_mentions_polyamide_in_composition() -> None:
    template = ListingTemplateRegistry().get_template("template-pull-tommy-femme")

    fields = ListingFields(
        model="",
        fr_size="L",
        us_w="",
        us_l="",
        fit_leg="",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="55",
        polyester_pct="",
        polyamide_pct="20",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="gris",
        knit_pattern="col V",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="PTF10",
    )

    _, description = template.render(fields)

    assert "20% polyamide" in description


def test_render_pull_tommy_femme_handles_unreadable_composition() -> None:
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
        cotton_pct="",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="PTF88",
    )

    _, description = template.render(fields)

    assert "Composition non lisible sur l'étiquette" in description


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
        polyamide_pct="",
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

    title, description = template.render(fields)

    assert (
        title
        == "Pull Tommy Hilfiger femme taille M en laine torsadée marron Made in Europe - PTF1"
    )
    assert title.lower().count("torsad") == 1
    assert "motif torsadé" in description.splitlines()[1].lower()
