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
from app.backend.templates import ListingTemplateRegistry
from app.backend.text_normalization import normalize_fit_terms


@pytest.fixture
def template_registry() -> ListingTemplateRegistry:
    return ListingTemplateRegistry()


def test_listing_fields_from_dict_requires_all_keys() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "cotton_pct": "99",
        "polyester_pct": "0",
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
        "cotton_pct": "99",
        "polyester_pct": "0",
        "elastane_pct": "1",
        "color_main": "bleu",
        "defects": "aucun défaut",
        "size_label_visible": True,
        "fabric_label_visible": True,
    }

    femme_payload = {**base_payload, "gender": "Femme", "sku": "JLF6"}
    homme_payload = {**base_payload, "gender": "Homme", "sku": "JLH12"}
    mix_payload = {**base_payload, "gender": "Mixte", "sku": "JLF3"}

    assert ListingFields.from_dict(femme_payload).sku == "JLF6"
    assert ListingFields.from_dict(homme_payload).sku == "JLH12"
    assert ListingFields.from_dict(mix_payload).sku == "JLF3"

    with pytest.raises(ValueError):
        ListingFields.from_dict({**base_payload, "gender": "Femme", "sku": "JLH7"})

    with pytest.raises(ValueError):
        ListingFields.from_dict({**base_payload, "gender": "Homme", "sku": "JLF9"})


def test_listing_fields_rejects_unknown_defect_tags() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "cotton_pct": "99",
        "polyester_pct": "0",
        "elastane_pct": "1",
        "gender": "Femme",
        "color_main": "bleu",
        "defects": "aucun défaut",
        "sku": "JLF6",
        "defect_tags": ["unknown"],
    }

    with pytest.raises(ValueError):
        ListingFields.from_dict(payload)


def test_listing_fields_parses_visibility_flags() -> None:
    payload = {
        "model": "501",
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "cotton_pct": "99",
        "polyester_pct": "0",
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


def test_listing_fields_normalizes_model_code() -> None:
    base_payload = {
        "fr_size": "38",
        "us_w": "28",
        "us_l": "30",
        "fit_leg": "bootcut",
        "rise_class": "haute",
        "cotton_pct": "99",
        "polyester_pct": "0",
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
        ("Skinny", ("Skinny/Slim", "skinny/slim", "slim")),
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
            "cotton_pct": "99",
            "polyester_pct": "0",
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
    assert "Entrejambe légèrement délavée, voir photos" in description
    assert "Étiquettes composition/taille coupées pour plus de confort." in description


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
            "cotton_pct": "99",
            "polyester_pct": "0",
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
    assert "Effets troués déchirés pour un style plus affirmé" in description
    assert "Effets troués pour plus style" not in description
    assert "Effets déchiré pour un style plus affirmé" not in description


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
        "cotton_pct": "99",
        "polyester_pct": "0",
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
    assert "Étiquette taille coupée pour plus de confort." in size_description

    fabric_hidden = ListingFields.from_dict(
        {**base_payload, "size_label_visible": True, "fabric_label_visible": False}
    )
    _title, fabric_description = template.render(fabric_hidden)
    assert "Étiquette composition coupée pour plus de confort." in fabric_description


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
            "cotton_pct": "60",
            "polyester_pct": "35",
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
    assert "60% coton, 35% polyester, 5% élasthanne" in description


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
        "cotton_pct": "99",
        "polyester_pct": "0",
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
            "cotton_pct": "99",
            "polyester_pct": "0",
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

    assert "Skinny/Slim" in result.title
    assert "skinny/slim" in result.description


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
            "cotton_pct": "99",
            "polyester_pct": "0",
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
            "cotton_pct": "99",
            "polyester_pct": "0",
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
            "cotton_pct": "99",
            "polyester_pct": "0",
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
    assert third_paragraph.startswith(
        "Très bon état Entrejambe légèrement délavée, voir photos"
    )
    assert "Très bon état général" not in third_paragraph

