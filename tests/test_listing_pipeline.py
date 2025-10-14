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
        "elastane_pct": "1",
        "gender": "femme",
        "color_main": "bleu",
        "defects": "aucun défaut",
        # sku intentionally missing
    }
    with pytest.raises(ValueError):
        ListingFields.from_dict(payload)


def test_normalize_fit_terms_applies_double_wording() -> None:
    title_term, description_term, hashtag_term = normalize_fit_terms("Bootcut")
    assert title_term == "évasé"
    assert description_term == "bootcut/évasé"
    assert hashtag_term == "bootcut"


def test_normalize_sizes_applies_business_rules() -> None:
    with_elastane: NormalizedSizes = normalize_sizes("28", "44", True)
    assert with_elastane.fr_size == "44"
    assert with_elastane.us_size is None
    assert with_elastane.note is not None

    regular: NormalizedSizes = normalize_sizes("28", "38", False)
    assert regular.fr_size == "38"
    assert regular.us_size == "28"
    assert regular.note is None


def test_template_render_injects_normalized_terms(template_registry: ListingTemplateRegistry) -> None:
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
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "très légères traces d'usure",
            "sku": "JLF6",
        }
    )

    title, description = template.render(fields)
    assert "évasé" in title
    assert "bootcut/évasé" in description
    assert "Mesure FR" not in description


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
            "elastane_pct": "1",
            "gender": "Femme",
            "color_main": "Bleu",
            "defects": "aucune anomalie",
            "sku": "JLF6",
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

    assert "skinny" in result.title
    assert "skinny/slim" in result.description

