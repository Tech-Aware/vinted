"""High-level tests for the listing generation helpers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.gpt_client import ListingGenerator
from app.backend.listing_fields import ListingFields
from app.backend.sizing import NormalizedSizes, normalize_sizes
from app.backend.templates import ListingTemplateRegistry, render_template_jean_levis_femme
from app.backend.text_normalization import normalize_fit_terms


@pytest.fixture
def template_registry() -> ListingTemplateRegistry:
    return ListingTemplateRegistry()


MEASUREMENT_EMPTY = {
    "bust_flat_measurement_cm": "",
    "length_measurement_cm": "",
    "sleeve_measurement_cm": "",
    "shoulder_measurement_cm": "",
    "waist_flat_measurement_cm": "",
    "hem_flat_measurement_cm": "",
}


SIZE_LABEL_CUT_MESSAGE = "Étiquette de taille coupée pour plus de confort."
COMPOSITION_LABEL_CUT_MESSAGE = "Étiquette de composition coupée pour plus de confort."
COMBINED_LABEL_CUT_MESSAGE = "Étiquettes de taille et composition coupées pour plus de confort."


def test_json_instruction_mentions_defect_synonyms() -> None:
    instruction = ListingFields.json_instruction()
    assert "faded_crotch" in instruction
    assert "entrejambe délavé" in instruction
    assert "stylish_holes" in instruction
    assert "effet troué" in instruction
    assert "waist_measurement_cm" in instruction
    assert "tour de taille" in instruction
    assert "viscose_pct" in instruction
    assert "nylon_pct" in instruction
    assert "acrylic_pct" in instruction
    assert "polyamide_pct" in instruction


def test_json_instruction_for_pull_tommy_mentions_new_fields() -> None:
    instruction = ListingFields.json_instruction("template-pull-tommy-femme")
    assert "wool_pct" in instruction
    assert "cashmere_pct" in instruction
    assert "knit_pattern" in instruction
    assert "PTF" in instruction
    assert "Made in Europe" in instruction
    assert "nylon_pct" in instruction
    assert "acrylic_pct" in instruction
    assert "polyamide_pct" in instruction
    assert "bust_flat_measurement_cm" in instruction
    assert "largeur de poitrine à plat" in instruction
    assert "length_measurement_cm" in instruction
    assert "sleeve_measurement_cm" in instruction
    assert "waist_flat_measurement_cm" in instruction
    assert "hem_flat_measurement_cm" in instruction
    assert "N'invente jamais de matière" in instruction
    assert "dans le titre" in instruction.lower()
    assert "la génération échouera" in instruction


def test_listing_fields_from_dict_requires_all_keys() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "viscose_pct": "0",
        "polyamide_pct": "",
        "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "femme",
        "color_main": "bleu",
        "defects": "aucun défaut",
        # sku intentionally missing
    }
    with pytest.raises(ValueError):
        ListingFields.from_dict(payload)


def test_listing_fields_enforces_sku_prefix_by_gender() -> None:
    base_payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "viscose_pct": "0",
        "polyamide_pct": "",
        "acrylic_pct": "",
        "elastane_pct": "1",
        "color_main": "bleu",
        "defects": "aucun défaut",
        "size_label_visible": True,
        "fabric_label_visible": True,
    }

    femme_payload = {**base_payload, "gender": "Femme", "sku": "JLF6"}
    homme_payload = {**base_payload, "gender": "Homme", "sku": "JLF12"}
    mix_payload = {**base_payload, "gender": "Mixte", "sku": "JLF3"}
    tommy_payload = {**base_payload, "gender": "Femme", "sku": "PTF7"}

    assert ListingFields.from_dict(femme_payload).sku == "JLF6"
    assert ListingFields.from_dict(homme_payload).sku == "JLF12"
    assert ListingFields.from_dict(mix_payload).sku == "JLF3"
    tommy_fields = ListingFields.from_dict(
        tommy_payload, template_name="template-pull-tommy-femme"
    )
    assert tommy_fields.sku == "PTF7"

    with pytest.raises(ValueError):
        ListingFields.from_dict(tommy_payload)

    with pytest.raises(ValueError):
        ListingFields.from_dict({**base_payload, "gender": "Femme", "sku": "JLH7"})

    with pytest.raises(ValueError):
        ListingFields.from_dict({**base_payload, "gender": "Homme", "sku": "JLH9"})

    with pytest.raises(ValueError):
        ListingFields.from_dict({**base_payload, "gender": "Homme", "sku": "PTF4"})


def test_listing_fields_rejects_unknown_defect_tags() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "viscose_pct": "0",
        "polyamide_pct": "",
        "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "bleu",
        "defects": "aucun défaut",
        "sku": "JLF6",
        "defect_tags": ["unknown"],
    }

    with pytest.raises(ValueError):
        ListingFields.from_dict(payload)


def test_listing_fields_splits_comma_separated_defect_tags() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "viscose_pct": "0",
        "polyamide_pct": "",
        "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "bleu",
        "defects": "effets d'usure stylés",
        "sku": "JLF6",
        "defect_tags": "stylish_holes, ripped",
    }

    fields = ListingFields.from_dict(payload)
    assert fields.defect_tags == ("stylish_holes", "ripped")


def test_listing_fields_parse_new_measurements_for_tommy_template() -> None:
    payload = {
        "model": "",
        "fr_size": "",
        "us_w": "",
        "us_l": "",
        "fit_leg": "",
        "rise_class": "",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "bust_flat_measurement_cm": "48,5 cm",
        "length_measurement_cm": "60",
        "sleeve_measurement_cm": "58 cm",
        "shoulder_measurement_cm": "38 cm",
        "waist_flat_measurement_cm": "46.0",
        "hem_flat_measurement_cm": "47",
        "cotton_pct": "100",
        "polyester_pct": "",
        "polyamide_pct": "",
        "viscose_pct": "",
        "acrylic_pct": "",
        "elastane_pct": "",
        "gender": "Femme",
        "color_main": "bleu",
        "defects": "",
        "sku": "PTF10",
        "size_label_visible": False,
        "fabric_label_visible": False,
    }

    fields = ListingFields.from_dict(
        payload, template_name="template-pull-tommy-femme"
    )

    assert fields.bust_flat_measurement_cm == pytest.approx(48.5)
    assert fields.length_measurement_cm == pytest.approx(60)
    assert fields.sleeve_measurement_cm == pytest.approx(58)
    assert fields.shoulder_measurement_cm == pytest.approx(38)
    assert fields.waist_flat_measurement_cm == pytest.approx(46)
    assert fields.hem_flat_measurement_cm == pytest.approx(47)

def test_listing_fields_parses_visibility_flags() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "viscose_pct": "0",
        "polyamide_pct": "",
        "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "bleu",
        "defects": "aucun défaut",
        "sku": "JLF6",
        "size_label_visible": "false",
        "fabric_label_visible": 0,
    }

    fields = ListingFields.from_dict(payload)
    assert fields.size_label_visible is False
    assert fields.fabric_label_visible is False


def test_listing_fields_parses_waist_measurement() -> None:
    payload = {
        "model": "501",
        "fr_size": "",
        "us_w": "",
        "us_l": "",
        "fit_leg": "slim",
        "rise_class": "",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "74,5",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "",
        "polyester_pct": "",
        "polyamide_pct": "",
        "viscose_pct": "",
        "acrylic_pct": "",
        "elastane_pct": "",
        "gender": "",
        "color_main": "",
        "defects": "",
        "defect_tags": [],
        "sku": "",
    }

    fields = ListingFields.from_dict(payload)
    assert fields.waist_measurement_cm == pytest.approx(74.5)


def test_listing_fields_defaults_visibility_flags_to_false() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "polyamide_pct": "",
        "viscose_pct": "0",
        "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "Bleu",
        "defects": "aucun défaut",
        "sku": "JLF6",
        "defect_tags": [],
    }

    fields = ListingFields.from_dict(payload)
    assert fields.size_label_visible is False
    assert fields.fabric_label_visible is False


@pytest.mark.parametrize(
    ("measurement", "expected"),
    [
        ("18", "basse"),
        ("23,5", "moyenne"),
        ("32", "haute"),
        ("34", "très haute"),
    ],
)
def test_listing_fields_resolves_rise_class_from_measurement(
    measurement: str, expected: str
) -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "",
        "rise_measurement_cm": measurement,
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "Bleu",
        "defects": "aucun défaut",
        "sku": "JLF6",
        "defect_tags": [],
        "size_label_visible": False,
        "fabric_label_visible": False,
    }

    fields = ListingFields.from_dict(payload)
    assert fields.resolved_rise_class == expected


def test_listing_fields_resolved_rise_class_handles_invalid_measurement() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "",
        "rise_measurement_cm": "non lisible",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "Bleu",
        "defects": "aucun défaut",
        "sku": "JLF6",
        "defect_tags": [],
        "size_label_visible": False,
        "fabric_label_visible": False,
    }

    fields = ListingFields.from_dict(payload)
    assert fields.resolved_rise_class == ""


def test_listing_fields_resolved_rise_class_prefers_explicit_value() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "20",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "Bleu",
        "defects": "aucun défaut",
        "sku": "JLF6",
        "defect_tags": [],
        "size_label_visible": False,
        "fabric_label_visible": False,
    }

    fields = ListingFields.from_dict(payload)
    assert fields.resolved_rise_class == "haute"


def test_listing_fields_resolved_rise_class_uses_measurement_even_when_label_visible() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "",
        "rise_measurement_cm": "28",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "Bleu",
        "defects": "aucun défaut",
        "sku": "JLF6",
        "defect_tags": [],
        "size_label_visible": True,
        "fabric_label_visible": False,
    }

    fields = ListingFields.from_dict(payload)
    assert fields.resolved_rise_class == "haute"


def test_listing_fields_infers_defect_tag_from_text() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "Bleu",
        "defects": "Entrejambe délavée visible",
        "sku": "JLF6",
        "defect_tags": [],
    }

    fields = ListingFields.from_dict(payload)
    assert fields.defect_tags == ("faded_crotch",)


def test_listing_fields_normalizes_model_code() -> None:
    base_payload = {
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "Bleu",
        "defects": "aucun défaut",
        "sku": "JLF6",
        "size_label_visible": True,
        "fabric_label_visible": True,
    }

    fields = ListingFields.from_dict({"model": "470 Signature super skinny", **base_payload})
    assert fields.model == "470"

    premium_fields = ListingFields.from_dict({"model": "501 premium stretch", **base_payload})
    assert premium_fields.model == "501 Premium"

    wedgie_fields = ListingFields.from_dict({"model": "Wedgie501 premium", **base_payload})
    assert wedgie_fields.model == "501 Premium"


@pytest.mark.parametrize(
    "fit_leg,expected",
    [
        ("Bootcut", ("Bootcut/Évasé", "bootcut/évasé", "bootcut")),
        ("bootcut / evase", ("Bootcut/Évasé", "bootcut/évasé", "bootcut")),
        ("Skinny", ("Skinny", "skinny", "slim")),
        ("droit", ("Straight/Droit", "straight/droit", "straight")),
    ],
)
def test_normalize_fit_terms_applies_double_wording(fit_leg: str, expected: tuple[str, str, str]) -> None:
    assert normalize_fit_terms(fit_leg) == expected


def test_normalize_sizes_applies_business_rules() -> None:
    with_elastane: NormalizedSizes = normalize_sizes("28", "44", True, ensure_even_fr=False)
    assert with_elastane.fr_size == "44"
    assert with_elastane.us_size is None
    assert with_elastane.note is not None

    regular: NormalizedSizes = normalize_sizes("28", "38", False, ensure_even_fr=False)
    assert regular.fr_size == "38"
    assert regular.us_size == "28"
    assert regular.note is None


def test_normalize_sizes_rounds_up_odd_us_when_requested() -> None:
    computed: NormalizedSizes = normalize_sizes("31", None, False, ensure_even_fr=True)
    assert computed.fr_size == "42"
    assert computed.us_size == "31"
    assert computed.note is None


def test_normalize_sizes_rounds_down_when_measurement_is_smaller() -> None:
    computed: NormalizedSizes = normalize_sizes(
        "31",
        None,
        False,
        ensure_even_fr=True,
        waist_measurement_cm=38,
    )
    assert computed.fr_size == "40"
    assert computed.us_size == "31"
    assert computed.note is None


def test_normalize_sizes_rounds_up_when_measurement_is_larger() -> None:
    computed: NormalizedSizes = normalize_sizes(
        "31",
        None,
        False,
        ensure_even_fr=True,
        waist_measurement_cm=44,
    )
    assert computed.fr_size == "42"
    assert computed.us_size == "31"
    assert computed.note is None


def test_normalize_sizes_falls_back_to_waist_measurement() -> None:
    computed: NormalizedSizes = normalize_sizes(
        None,
        None,
        False,
        ensure_even_fr=True,
        waist_measurement_cm=74,
    )
    assert computed.fr_size == "74"
    assert computed.us_size is None
    assert computed.note is not None
    assert "74 cm" in computed.note


def test_normalize_sizes_prefers_measurement_when_conflict() -> None:
    computed: NormalizedSizes = normalize_sizes(
        "28",
        "38",
        False,
        ensure_even_fr=True,
        waist_measurement_cm=74,
    )
    assert computed.fr_size == "74"
    assert computed.us_size is None
    assert computed.note is not None
    assert "74 cm" in computed.note


def test_normalize_sizes_prefers_measurement_when_gap_is_smaller() -> None:
    computed: NormalizedSizes = normalize_sizes(
        "31",
        None,
        False,
        ensure_even_fr=True,
        waist_measurement_cm=30,
    )
    assert computed.fr_size == "30"
    assert computed.us_size is None
    assert computed.note is not None
    assert "30 cm" in computed.note


def test_template_render_injects_normalized_terms(template_registry: ListingTemplateRegistry) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "38",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "bootcut / evase",
            "rise_class": "haute",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "très légères traces d'usure",
            "sku": "JLF6",
            "defect_tags": ["faded_crotch"],
            "size_label_visible": False,
            "fabric_label_visible": False,
        }
    )

    title, description = template.render(fields)
    assert "Bootcut/Évasé" in title
    assert "bootcut/évasé" in description
    assert "haute" not in title.lower()
    assert "taille haute" in description.lower()
    assert "Mesure FR" not in description
    assert " W" not in title  # no US size injected when label is hidden
    assert " L30" not in title
    assert description.count(COMBINED_LABEL_CUT_MESSAGE) == 1
    assert "Très bon état : entrejambe légèrement délavée (voir photos)" in description
    assert COMPOSITION_LABEL_CUT_MESSAGE not in description
    assert SIZE_LABEL_CUT_MESSAGE not in description


def test_render_template_prefers_measurement_when_conflict(
    template_registry: ListingTemplateRegistry,
) -> None:
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "38",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "bootcut",
            "rise_class": "haute",
            "rise_measurement_cm": "",
            **MEASUREMENT_EMPTY,
            "waist_measurement_cm": "74",
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "0",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "aucun défaut",
            "sku": "JLF6",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": False,
        }
    )

    title, description = render_template_jean_levis_femme(fields)

    assert "FR74" in title
    assert "W28" not in title
    assert "Taille 74 FR" in description
    assert "Taille 28 US" not in description
    assert "(voir photos)" in description
    assert "Taille estimée à partir" not in description


def test_template_render_translates_main_color_to_french(
    template_registry: ListingTemplateRegistry,
) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "38",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "bootcut",
            "rise_class": "haute",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "black",
            "defects": "aucun défaut",
            "sku": "JLF6",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": True,
        }
    )

    title, description = template.render(fields)

    assert "noir" in title
    assert "Coloris noir" in description
    assert "#jeannoir" in description


def test_template_render_handles_viscose_composition(
    template_registry: ListingTemplateRegistry,
) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "724",
            "fr_size": "40",
            "us_w": "30",
            "us_l": "32",
            "fit_leg": "straight",
            "rise_class": "moyenne",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "60",
            "polyester_pct": "10",
            "polyamide_pct": "",
            "viscose_pct": "30",
            "acrylic_pct": "",
            "elastane_pct": "0",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "aucun défaut",
            "sku": "JLF15",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": True,
        }
    )

    title, description = template.render(fields)
    assert fields.has_viscose is True
    assert "30% viscose" not in title
    assert "60% coton" in title
    assert "Composition : 60% coton, 30% viscose et 10% polyester." in description


def test_template_render_mentions_wool_cashmere_nylon(
    template_registry: ListingTemplateRegistry,
) -> None:
    template = template_registry.get_template("template-jean-levis-femme")
    fields = ListingFields.from_dict(
        {
            "model": "721",
            "fr_size": "38",
            "us_w": "28",
            "us_l": "32",
            "fit_leg": "slim",
            "rise_class": "moyenne",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "70",
            "wool_pct": "20",
            "cashmere_pct": "5",
            "nylon_pct": "5",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "0",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "aucun défaut",
            "sku": "JLF7",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": True,
        }
    )

    _title, description = template.render(fields)
    assert (
        "Composition : 70% coton, 20% laine, 5% cachemire et 5% nylon." in description
    )


def test_template_render_combines_related_defects(template_registry: ListingTemplateRegistry) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "38",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "bootcut",
            "rise_class": "haute",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "traces stylées",
            "sku": "JLF6",
            "defect_tags": ["stylish_holes", "ripped"],
            "size_label_visible": True,
            "fabric_label_visible": True,
        }
    )

    _title, description = template.render(fields)
    assert (
        "Très bon état : Quelques trous discrets et effets déchirés (voir photos)"
        in description
    )
    assert "effets troués pour un style plus affirmé" not in description
    assert "effets déchirés pour un style plus affirmé" not in description


def test_template_pull_tommy_mentions_nylon_and_acrylic(
    template_registry: ListingTemplateRegistry,
) -> None:
    template = template_registry.get_template("template-pull-tommy-femme")
    fields = ListingFields.from_dict(
        {
            "model": "",
            "fr_size": "M",
            "us_w": "",
            "us_l": "",
            "fit_leg": "",
            "rise_class": "",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "65",
            "wool_pct": "25",
            "cashmere_pct": "5",
            "nylon_pct": "5",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "5",
            "elastane_pct": "0",
            "gender": "Femme",
            "color_main": "Marine",
            "defects": "",
            "sku": "PTF2",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": True,
            "knit_pattern": "torsadé",
            "made_in": "Made in Italy",
        },
        template_name="template-pull-tommy-femme",
    )

    _title, description = template.render(fields)
    assert (
        "Composition : 65% coton, 25% laine, 5% cachemire, 5% acrylique et 5% nylon." in description
    )


def test_template_render_mentions_missing_labels_individually(
    template_registry: ListingTemplateRegistry,
) -> None:
    template = template_registry.get_template(template_registry.default_template)
    base_payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "Bleu",
        "defects": "aucune anomalie",
        "sku": "JLF6",
        "defect_tags": [],
    }

    size_hidden = ListingFields.from_dict(
        {**base_payload, "size_label_visible": False, "fabric_label_visible": True}
    )
    _title, size_description = template.render(size_hidden)
    assert SIZE_LABEL_CUT_MESSAGE in size_description

    fabric_hidden = ListingFields.from_dict(
        {**base_payload, "size_label_visible": True, "fabric_label_visible": False}
    )
    _title, fabric_description = template.render(fabric_hidden)
    assert COMPOSITION_LABEL_CUT_MESSAGE in fabric_description


def test_template_render_uses_waist_measurement_when_label_hidden(
    template_registry: ListingTemplateRegistry,
) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "",
            "us_w": "",
            "us_l": "",
            "fit_leg": "straight",
            "rise_class": "moyenne",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "74",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "aucun défaut",
            "sku": "",
            "defect_tags": [],
            "size_label_visible": False,
            "fabric_label_visible": False,
        }
    )

    title, description = template.render(fields)

    assert "FR74" in title
    assert "Taille 74 FR" in description
    assert description.count(COMBINED_LABEL_CUT_MESSAGE) == 1
    assert COMPOSITION_LABEL_CUT_MESSAGE not in description
    assert SIZE_LABEL_CUT_MESSAGE not in description


def test_template_render_mentions_polyester(template_registry: ListingTemplateRegistry) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "40",
            "us_w": "30",
            "us_l": "30",
            "fit_leg": "slim",
            "rise_class": "moyenne",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "60",
            "polyester_pct": "35",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "5",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "aucune anomalie",
            "sku": "JLF8",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": True,
        }
    )

    assert fields.has_polyester is True
    _title, description = template.render(fields)
    assert "Composition : 60% coton, 35% polyester et 5% élasthanne." in description


def test_template_render_skips_composition_when_label_missing(
    template_registry: ListingTemplateRegistry,
) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "38",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "bootcut",
            "rise_class": "haute",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "aucune anomalie",
            "sku": "JLF6",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": False,
        }
    )

    title, description = template.render(fields)
    assert "coton" not in title.lower()
    assert description.count(COMPOSITION_LABEL_CUT_MESSAGE) == 1
    assert COMBINED_LABEL_CUT_MESSAGE not in description
    assert SIZE_LABEL_CUT_MESSAGE not in description
    assert "% polyester" not in description
    assert "% élasthanne" not in description


def test_listing_fields_resets_fiber_flags_when_label_missing() -> None:
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "38",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "bootcut",
            "rise_class": "haute",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "12",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "2",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "aucune anomalie",
            "sku": "JLF6",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": False,
        }
    )

    assert fields.has_polyester is False
    assert fields.has_elastane is False
    assert fields.has_viscose is False


@pytest.mark.parametrize("model_value", [None, ""])
def test_template_render_omits_model_when_missing(
    template_registry: ListingTemplateRegistry, model_value: str | None
) -> None:
    template = template_registry.get_template(template_registry.default_template)
    payload = {
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
        "cotton_pct": "99",
        "polyester_pct": "0",
        "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "Bleu",
        "defects": "aucune anomalie",
        "sku": "JLF6",
        "defect_tags": [],
        "size_label_visible": True,
        "fabric_label_visible": True,
        "model": model_value,
    }

    fields = ListingFields.from_dict(payload)
    title, description = template.render(fields)

    assert "  " not in title
    assert not title.startswith("Jean Levi’s  ")
    assert title.split()[0:2] == ["Jean", "Levi’s"]

    first_paragraph = description.split("\n\n")[0]
    first_sentence = first_paragraph.split("\n")[0]
    assert first_sentence == "Jean Levi’s pour Femme."
    assert "modèle" not in first_sentence


def test_template_render_avoids_defaulting_missing_fields(
    template_registry: ListingTemplateRegistry,
) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "",
            "fr_size": "",
            "us_w": "",
            "us_l": "",
            "fit_leg": "",
            "rise_class": "",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "",
            "polyester_pct": "",
            "polyamide_pct": "",
            "viscose_pct": "",
            "acrylic_pct": "",
            "elastane_pct": "",
            "gender": "",
            "color_main": "",
            "defects": "",
            "sku": "",
            "defect_tags": [],
            "size_label_visible": False,
            "fabric_label_visible": False,
        }
    )

    title, description = template.render(fields)
    assert "femme" not in title.lower()
    assert "bleu" not in title.lower()
    assert "femme" not in description.lower()
    assert "bleu" not in description.lower()
    assert "taille non précisée" in description.lower()
    assert "coupe non précisée" in description.lower()


def test_generator_parses_json_and_renders(template_registry: ListingTemplateRegistry) -> None:
    template = template_registry.get_template(template_registry.default_template)
    generator = ListingGenerator(model="test-model", api_key="dummy")

    class _FakeContent:
        def __init__(self, text: str) -> None:
            self.text = text

    class _FakeBlock:
        def __init__(self, text: str) -> None:
            self.content = [_FakeContent(text)]

    class _FakeResponse:
        def __init__(self, text: str) -> None:
            self.output = [_FakeBlock(text)]

    fields_json = {
        "fields": {
            "model": "501",
            "fr_size": "44",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "slim",
            "rise_class": "moyenne",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "aucune anomalie",
            "sku": "JLF6",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": True,
        }
    }

    class _FakeResponses:
        def __init__(self, text: str) -> None:
            self._text = text

        def create(self, **_kwargs: object) -> _FakeResponse:
            return _FakeResponse(self._text)

    class _FakeClient:
        def __init__(self, text: str) -> None:
            self.responses = _FakeResponses(text)

    json_text = json.dumps(fields_json)
    generator._client = _FakeClient(json_text)  # type: ignore[attr-defined]

    result = generator.generate_listing([], "", template)

    assert "Skinny" in result.title
    assert "skinny" in result.description


def test_generator_tolerates_invalid_levis_sku(template_registry: ListingTemplateRegistry) -> None:
    template = template_registry.get_template("template-jean-levis-femme")
    generator = ListingGenerator(model="test-model", api_key="dummy")

    class _FakeContent:
        def __init__(self, text: str) -> None:
            self.text = text

    class _FakeBlock:
        def __init__(self, text: str) -> None:
            self.content = [_FakeContent(text)]

    class _FakeResponse:
        def __init__(self, text: str) -> None:
            self.output = [_FakeBlock(text)]

    invalid_fields_json = {
        "fields": {
            "model": "501",
            "fr_size": "44",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "slim",
            "rise_class": "moyenne",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
            **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "aucune anomalie",
            "sku": "PTF12",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": True,
        }
    }

    class _FakeResponses:
        def __init__(self, text: str) -> None:
            self._text = text

        def create(self, **_kwargs: object) -> _FakeResponse:
            return _FakeResponse(self._text)

    class _FakeClient:
        def __init__(self, text: str) -> None:
            self.responses = _FakeResponses(text)

    generator._client = _FakeClient(json.dumps(invalid_fields_json))  # type: ignore[attr-defined]

    result = generator.generate_listing([], "", template)

    assert result.sku_missing is True


def test_template_render_falls_back_to_free_text(template_registry: ListingTemplateRegistry) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "38",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "bootcut",
            "rise_class": "haute",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "usure légère sur la poche arrière",
            "sku": "JLF6",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": True,
        }
    )

    _title, description = template.render(fields)
    assert "usure légère sur la poche arrière" in description


def test_template_render_ignores_positive_defect_phrase(
    template_registry: ListingTemplateRegistry,
) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "38",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "bootcut",
            "rise_class": "haute",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "Très bon état",
            "sku": "JLF6",
            "defect_tags": [],
            "size_label_visible": True,
            "fabric_label_visible": True,
        }
    )

    _title, description = template.render(fields)
    third_paragraph = description.split("\n\n")[2].split("\n")[0]
    assert third_paragraph == "Très bon état"


def test_template_render_mentions_catalog_defect_without_duplication(
    template_registry: ListingTemplateRegistry,
) -> None:
    template = template_registry.get_template(template_registry.default_template)
    fields = ListingFields.from_dict(
        {
            "model": "501",
            "fr_size": "38",
            "us_w": "28",
            "us_l": "30",
            "fit_leg": "bootcut",
            "rise_class": "haute",
            "rise_measurement_cm": "",
            "waist_measurement_cm": "",
        **MEASUREMENT_EMPTY,
            "cotton_pct": "99",
            "polyester_pct": "0",
            "polyamide_pct": "",
            "viscose_pct": "0",
            "acrylic_pct": "",
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "",
            "sku": "JLF6",
            "defect_tags": ["faded_crotch"],
            "size_label_visible": True,
            "fabric_label_visible": True,
        }
    )

    _title, description = template.render(fields)
    third_paragraph = description.split("\n\n")[2].split("\n")[0]
    assert third_paragraph == "Très bon état : entrejambe légèrement délavée (voir photos)"
    assert "Très bon état général" not in third_paragraph

