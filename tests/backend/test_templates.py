"""Tests for listing templates rendering."""
from __future__ import annotations

import sys
import json
from dataclasses import asdict
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.gpt_client import ListingGenerator
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

    _title, description = template.render(fields)

    assert "sku" not in description.lower()

    generator = ListingGenerator()
    payload = {"fields": asdict(fields)}

    class _FakeResponse:
        def __init__(self, text: str) -> None:
            self.output_text = text

    class _FakeResponses:
        def __init__(self, text: str) -> None:
            self._text = text

        def create(self, **_kwargs: object) -> _FakeResponse:
            return _FakeResponse(self._text)

    class _FakeClient:
        def __init__(self, text: str) -> None:
            self.responses = _FakeResponses(text)

    generator._client = _FakeClient(json.dumps(payload))  # type: ignore[attr-defined]
    result = generator.generate_listing([], "", template)

    assert result.sku_missing is True


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

    assert description.count("Étiquettes coupées pour plus de confort.") == 1


def test_render_jean_levis_marks_estimated_size_without_forbidden_note() -> None:
    template = ListingTemplateRegistry().get_template("template-jean-levis-femme")
    fields = ListingFields(
        model="",  # no explicit context
        fr_size="",
        us_w="",
        us_l="",
        fit_leg="straight",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=41.2,
        cotton_pct="",  # composition irrelevant here
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="Femme",
        color_main="",
        defects="",
        defect_tags=(),
        size_label_visible=False,
        fabric_label_visible=False,
        fabric_label_cut=False,
        sku="JLF22",
    )

    title, description = template.render(fields)

    assert "(voir photos)" in description
    assert "Taille estimée à partir" not in title
    assert "Taille estimée à partir" not in description


def test_render_jean_levis_fabric_label_missing_no_duplicate_messages() -> None:
    template = ListingTemplateRegistry().get_template("template-jean-levis-femme")
    fields = ListingFields(
        model="",  # minimal context
        fr_size="38",
        us_w="28",
        us_l="",
        fit_leg="slim",
        rise_class="",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="Femme",
        color_main="",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=False,
        fabric_label_cut=False,
        sku="JLF23",
    )

    _, description = template.render(fields)

    assert description.count("Étiquette composition non visible sur les photos.") == 1
    assert "Étiquettes coupées pour plus de confort." not in description


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

    assert description.count("Étiquette composition non visible sur les photos.") == 1
    assert "Étiquettes coupées pour plus de confort." not in description
    assert "Étiquette taille non visible sur les photos." not in description
    assert "Étiquettes taille et composition non visibles sur les photos." in description


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


def test_render_pull_tommy_femme_estimates_size_from_bust_measurement() -> None:
    template = ListingTemplateRegistry().get_template("template-pull-tommy-femme")
    fields = ListingFields(
        model="",
        fr_size="",
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
        color_main="bleu marine",
        defects="",
        defect_tags=(),
        size_label_visible=False,
        fabric_label_visible=False,
        sku="",
        knit_pattern="",
        made_in="",
        bust_flat_measurement_cm=48.0,
        length_measurement_cm=50.0,
        sleeve_measurement_cm=61.0,
        shoulder_measurement_cm=39.0,
        waist_flat_measurement_cm=46.0,
        hem_flat_measurement_cm=47.0,
    )

    title, description = template.render(fields)

    assert "taille L" in title
    assert "estimée" not in title

    first_paragraph_lines = description.split("\n\n")[0].split("\n")
    assert first_paragraph_lines[0] == (
        "Pull Tommy Hilfiger pour femme taille L (Taille estimée depuis un tour de poitrine ~96 cm (largeur à plat x2). longueur épaule-ourlet ~50 cm)."
    )

    assert "Taille estimée depuis un tour de poitrine ~96 cm (largeur à plat x2)." in first_paragraph_lines[0]
    assert "Coupe courte" not in description
    assert "Manches mesurées" not in description

    assert description.count("Étiquettes coupées pour plus de confort.") == 1
    assert "Mesures à plat disponibles" not in description
    assert "#durin31tfL" in description


def test_render_pull_tommy_femme_estimates_size_from_full_circumference() -> None:
    template = ListingTemplateRegistry().get_template("template-pull-tommy-femme")
    fields = ListingFields(
        model="",
        fr_size="",
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
        color_main="bleu marine",
        defects="",
        defect_tags=(),
        size_label_visible=False,
        fabric_label_visible=False,
        sku="",
        knit_pattern="",
        made_in="",
        bust_flat_measurement_cm=96.0,
        length_measurement_cm=None,
        sleeve_measurement_cm=None,
        shoulder_measurement_cm=None,
        waist_flat_measurement_cm=None,
        hem_flat_measurement_cm=None,
    )

    title, description = template.render(fields)

    assert "taille L" in title

    first_sentence = description.split("\n\n")[0].split("\n")[0]
    assert first_sentence == (
        "Pull Tommy Hilfiger pour femme taille L (Taille estimée depuis un tour de poitrine ~96 cm.)."
    )

    hashtags_line = description.splitlines()[-1]
    hashtags = [token for token in hashtags_line.split() if token.startswith("#")]
    assert "#durin31tfL" in hashtags


def test_render_pull_tommy_femme_splits_neckline_from_pattern() -> None:
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
        cotton_pct="60",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="bleu marine",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="PTF02",
        knit_pattern="Marinière col V",
    )

    title, description = template.render(fields)

    assert title.startswith("Pull Tommy Hilfiger femme taille M")
    assert title.split(" - ")[0].endswith("col V")

    first_paragraph_lines = description.split("\n\n")[0].split("\n")
    assert first_paragraph_lines[1] == (
        "Motif marinière sur un coloris bleu marine facile à associer. "
        "Col V qui structure joliment l'encolure."
    )

    highlight_line = description.split("\n\n")[1].split("\n")[0]
    assert highlight_line == (
        "Maille composée de 60% coton pour une sensation douce et respirante. "
        "L'esprit marinière signe une allure marine iconique. Col V pour une jolie finition."
    )


def test_render_pull_tommy_femme_omits_irrelevant_bust_measurement() -> None:
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
        color_main="bleu marine",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="PTF03",
        knit_pattern="",
        bust_flat_measurement_cm=47.0,
        length_measurement_cm=55.0,
        sleeve_measurement_cm=60.0,
        shoulder_measurement_cm=38.0,
        waist_flat_measurement_cm=45.0,
        hem_flat_measurement_cm=46.0,
    )

    _, description = template.render(fields)

    first_line = description.split("\n\n")[0].split("\n")[0]
    assert "poitrine" not in first_line.lower()

    measurement_section = description.split("\n\n")[2]
    assert "Poitrine" not in measurement_section


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

    assert description.count("Étiquettes coupées pour plus de confort.") == 1
    assert "Référence SKU" not in description


def test_render_pull_tommy_femme_skips_cut_sentence_when_other_labels_visible() -> None:
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
        non_size_labels_visible=True,
        sku="PTF97",
    )

    _, description = template.render(fields)

    assert description.count("Étiquettes coupées pour plus de confort.") == 1
    assert "Composition non lisible sur l'étiquette (voir photos pour confirmation)." not in description


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


def test_render_pull_tommy_femme_handles_dress() -> None:
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
        cotton_pct="70",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="",
        color_main="rouge",
        knit_pattern="",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="PTF77",
        is_dress=True,
    )

    title, description = template.render(fields)

    assert title.startswith("Robe Tommy Hilfiger femme")
    first_paragraph_lines = description.split("\n\n")[0].split("\n")
    assert first_paragraph_lines[0] == "Robe Tommy Hilfiger pour femme taille M."

    fourth_paragraph = description.split("\n\n")[3]
    assert "mes robes Tommy femme" in fourth_paragraph

    hashtags_line = description.splitlines()[-1]
    assert "#robetommy" in hashtags_line
    assert "#robefemme" in hashtags_line
    assert "#pulltommy" not in hashtags_line
    assert "#gilettommy" not in hashtags_line


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
    assert "maille torsadée" in description.splitlines()[1].lower()


@pytest.mark.parametrize(
    (
        "pattern",
        "expected_marketing_fragment",
        "expected_style_sentence",
        "expected_hashtags",
        "extra_fields",
        "expected_material_segment",
    ),
    [
        (
            "Losanges écossais",
            "Les losanges écossais apportent une touche preppy iconique.",
            "Motif argyle chic qui dynamise la silhouette.",
            ["#pulllosange", "#argyle"],
            {},
            None,
        ),
        (
            "Rayé",
            "Les rayures dynamisent la silhouette.",
            "Les rayures insufflent une allure graphique intemporelle.",
            ["#pullrayure", "#rayures"],
            {},
            None,
        ),
        (
            "Motif chevron",
            "Le motif chevron structure le look avec élégance.",
            "Motif chevron travaillé pour une allure sophistiquée.",
            ["#pullchevron"],
            {},
            None,
        ),
        (
            "Motif damier",
            "Le motif damier apporte une touche graphique affirmée.",
            "Damier contrasté pour un twist visuel fort.",
            ["#pulldamier"],
            {},
            None,
        ),
        (
            "Motif jacquard",
            "La maille jacquard dévoile un motif travaillé très cosy.",
            "Jacquard riche en détails pour une allure chaleureuse.",
            ["#pulljacquard", "#fairisle"],
            {},
            None,
        ),
        (
            "Torsadé",
            "Les torsades apportent du relief cosy.",
            "Maille torsadée iconique au charme artisanal.",
            ["#pulltorsade"],
            {"cotton_pct": "", "wool_pct": "60"},
            "en laine torsadée",
        ),
        (
            "Point de riz",
            "La texture en relief apporte du volume et de la douceur.",
            "Maille texturée qui joue sur les reliefs délicats.",
            ["#pulltexturé"],
            {},
            None,
        ),
        (
            "Pied-de-poule",
            "Le motif pied-de-poule signe une allure rétro-chic.",
            "Pied-de-poule graphique pour une silhouette élégante.",
            ["#pullpieddepoule"],
            {},
            None,
        ),
        (
            "Motif nordique",
            "L’esprit nordique réchauffe vos looks d’hiver.",
            "Motif nordique douillet esprit chalet.",
            ["#pullnordique"],
            {},
            None,
        ),
        (
            "Motif bohème",
            "Le motif bohème diffuse une vibe folk et décontractée.",
            "Motif bohème pour une allure folk décontractée.",
            ["#pullboheme"],
            {},
            None,
        ),
        (
            "Color block",
            "Le color block joue sur les contrastes audacieux.",
            "Color block énergique qui capte l’œil.",
            ["#pullcolorblock"],
            {},
            None,
        ),
        (
            "Dégradé",
            "Le dégradé nuance la maille avec subtilité.",
            "Dégradé vaporeux pour un rendu tout en douceur.",
            ["#pulldegrade"],
            {},
            None,
        ),
        (
            "Logo TH",
            "Le logo mis en avant affirme le style Tommy.",
            "Logo signature mis en valeur pour un look assumé.",
            ["#pulllogo"],
            {},
            None,
        ),
        (
            "Motif graphique",
            "Le motif graphique apporte une touche arty.",
            "Graphismes audacieux pour une silhouette arty.",
            ["#pullgraphique"],
            {},
            None,
        ),
        (
            "Motif inattendu",
            "Motif motif inattendu pour une touche originale.",
            "Motif motif inattendu sur un coloris bleu facile à associer.",
            [],
            {},
            None,
        ),
    ],
)
def test_render_pull_tommy_femme_pattern_specific_rules(
    pattern: str,
    expected_marketing_fragment: str,
    expected_style_sentence: str,
    expected_hashtags: list[str],
    extra_fields: dict[str, object],
    expected_material_segment: str | None,
) -> None:
    template = ListingTemplateRegistry().get_template("template-pull-tommy-femme")

    base_fields = {
        "model": "",
        "fr_size": "M",
        "us_w": "",
        "us_l": "",
        "fit_leg": "",
        "rise_class": "",
        "rise_measurement_cm": None,
        "waist_measurement_cm": None,
        "cotton_pct": "70",
        "polyester_pct": "",
        "polyamide_pct": "",
        "viscose_pct": "",
        "elastane_pct": "",
        "gender": "",
        "color_main": "bleu",
        "defects": "",
        "defect_tags": (),
        "size_label_visible": True,
        "fabric_label_visible": True,
        "sku": "PTFRULE",
        "knit_pattern": pattern,
    }
    base_fields.update(extra_fields)
    fields = ListingFields(**base_fields)

    title, description = template.render(fields)
    paragraphs = description.split("\n\n")
    marketing_line = paragraphs[1].splitlines()[0]
    style_line = paragraphs[0].splitlines()[1]
    hashtags_line = paragraphs[-1]

    assert expected_marketing_fragment in marketing_line
    assert style_line == expected_style_sentence
    for tag in expected_hashtags:
        assert tag in hashtags_line

    if expected_material_segment:
        assert expected_material_segment in title
