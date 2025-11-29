"""Unit tests for the targeted SKU recovery logic."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.gpt_client import ListingGenerator
from app.backend.listing_fields import ListingFields
from app.backend.templates import ListingTemplate


class FakeResponse:
    """Minimal response object exposing the text payload."""

    def __init__(self, text: str) -> None:
        self.output_text = text


class FakeResponses:
    def __init__(self, outputs: List[FakeResponse]) -> None:
        self._outputs = list(outputs)
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        if not self._outputs:
            raise AssertionError("No more fake responses configured")
        self.calls.append(kwargs)
        return self._outputs.pop(0)


class FakeClient:
    def __init__(self, outputs: List[FakeResponse]) -> None:
        self.responses = FakeResponses(outputs)


_DEFECTS_KEY = "defects"


def _base_fields_payload(**overrides: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": "",
        "fr_size": "M",
        "us_w": "",
        "us_l": "",
        "fit_leg": "",
        "rise_class": "",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        "cotton_pct": "100",
        "polyester_pct": "",
        "polyamide_pct": "",
        "viscose_pct": "",
        "elastane_pct": "",
        "nylon_pct": "",
        "acrylic_pct": "",
        "bust_flat_measurement_cm": "",
        "length_measurement_cm": "",
        "sleeve_measurement_cm": "",
        "shoulder_measurement_cm": "",
        "waist_flat_measurement_cm": "",
        "hem_flat_measurement_cm": "",
        "gender": "Femme",
        "color_main": "Bleu",
        _DEFECTS_KEY: "",
        "defect_tags": [],
        "size_label_visible": False,
        "fabric_label_visible": False,
        "fabric_label_cut": False,
        "sku": "",
        "wool_pct": "",
        "cashmere_pct": "",
        "knit_pattern": "",
        "made_in": "",
        "is_cardigan": False,
        "is_dress": False,
    }
    payload.update(overrides)
    return payload


def _listing_response(fields: Dict[str, Any]) -> FakeResponse:
    return FakeResponse(json.dumps({"fields": fields}))


def _polaire_fields_payload(**overrides: Any) -> Dict[str, Any]:
    payload = _base_fields_payload(
        cotton_pct="",
        polyester_pct="100",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        acrylic_pct="",
    )
    payload.update(
        {
            "brand": "The North Face",
            "zip_style": "",
            "feature_notes": "",
            "technical_features": "",
            "has_hood": False,
            "neckline_style": "",
            "special_logo": "",
            "non_size_labels_visible": False,
        }
    )
    payload.update(overrides)
    return payload


def _build_template(captured: Dict[str, Any]) -> ListingTemplate:
    def _render(fields):
        captured["fields"] = fields
        return ("TITLE", f"DESC-{fields.sku}")

    return ListingTemplate(
        name="template-pull-tommy-femme",
        description="",
        prompt="PROMPT",
        render_callback=_render,
    )


def _build_template_with_size_capture(captured: Dict[str, Any]) -> ListingTemplate:
    def _render(fields):
        captured["fields"] = fields
        return (f"TITRE-{fields.fr_size}", "DESC")

    return ListingTemplate(
        name="template-pull-tommy-femme",
        description="",
        prompt="PROMPT",
        render_callback=_render,
    )


@pytest.mark.parametrize(
    "sku_reply,expected",
    [
        ("PTF52", "PTF52"),
        ("ptf7 ", "PTF7"),
        ("```plaintext\nptf91\n```", "PTF91"),
    ],
)
def test_generate_listing_recovers_tommy_sku(
    monkeypatch: pytest.MonkeyPatch, sku_reply: str, expected: str
) -> None:
    monkeypatch.setattr("app.backend.gpt_client.OpenAI", object)
    main_response = _listing_response(_base_fields_payload())
    recovery_response = FakeResponse(sku_reply)
    fake_client = FakeClient([main_response, recovery_response])

    generator = ListingGenerator(model="fake", api_key="test")
    generator._client = fake_client  # type: ignore[assignment]

    captured: Dict[str, Any] = {}
    template = _build_template(captured)

    result = generator.generate_listing(["data:image/png;base64,AAA"], "", template, "")

    assert result.title == "TITLE"
    fields = captured.get("fields")
    assert fields is not None
    assert fields.sku == expected
    assert len(fake_client.responses.calls) == 2
    second_call = fake_client.responses.calls[1]
    targeted_prompt = second_call["input"][1]["content"][-1]["text"]
    assert "Repère le SKU Tommy Hilfiger" in targeted_prompt


def test_generate_listing_raises_when_recovery_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.backend.gpt_client.OpenAI", object)
    main_response = _listing_response(_base_fields_payload())
    recovery_response = FakeResponse("")
    fake_client = FakeClient([main_response, recovery_response])

    generator = ListingGenerator(model="fake", api_key="test")
    generator._client = fake_client  # type: ignore[assignment]

    template = _build_template({})

    with pytest.raises(ValueError, match="Impossible de récupérer un SKU Tommy Hilfiger lisible"):
        generator.generate_listing(["data:image/png;base64,BBB"], "", template, "")

    assert len(fake_client.responses.calls) == 2


def test_listing_fields_allows_missing_measurements_for_levis() -> None:
    payload = _base_fields_payload(sku="JLF10", gender="Femme")
    for key in (
        "bust_flat_measurement_cm",
        "length_measurement_cm",
        "sleeve_measurement_cm",
        "shoulder_measurement_cm",
        "waist_flat_measurement_cm",
        "hem_flat_measurement_cm",
    ):
        payload.pop(key, None)

    fields = ListingFields.from_dict(
        payload, template_name="template-jean-levis-femme"
    )

    assert fields.bust_flat_measurement_cm is None
    assert fields.length_measurement_cm is None
    assert fields.sleeve_measurement_cm is None
    assert fields.shoulder_measurement_cm is None
    assert fields.waist_flat_measurement_cm is None
    assert fields.hem_flat_measurement_cm is None


def test_comment_overrides_fr_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.backend.gpt_client.OpenAI", object)
    payload = _base_fields_payload(fr_size="40", sku="PTF1")
    main_response = _listing_response(payload)
    fake_client = FakeClient([main_response])

    generator = ListingGenerator(model="fake", api_key="test")
    generator._client = fake_client  # type: ignore[assignment]

    captured: Dict[str, Any] = {}
    template = _build_template_with_size_capture(captured)

    result = generator.generate_listing(
        ["data:image/png;base64,AAA"], "taille FR38, coupe droite", template, ""
    )

    assert result.title == "TITRE-38"
    fields = captured.get("fields")
    assert fields is not None
    assert fields.fr_size == "38"


def test_comment_without_explicit_size_keeps_model_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.backend.gpt_client.OpenAI", object)
    payload = _base_fields_payload(fr_size="40", sku="PTF1")
    main_response = _listing_response(payload)
    fake_client = FakeClient([main_response])

    generator = ListingGenerator(model="fake", api_key="test")
    generator._client = fake_client  # type: ignore[assignment]

    captured: Dict[str, Any] = {}
    template = _build_template_with_size_capture(captured)

    result = generator.generate_listing(
        ["data:image/png;base64,AAA"], "Coupe droite sans précision de taille", template, ""
    )

    assert result.title == "TITRE-40"
    fields = captured.get("fields")
    assert fields is not None
    assert fields.fr_size == "40"


def test_comment_with_defect_information_overrides_defects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.backend.gpt_client.OpenAI", object)
    payload = _base_fields_payload(defects="", sku="PTF1")
    main_response = _listing_response(payload)
    fake_client = FakeClient([main_response])

    generator = ListingGenerator(model="fake", api_key="test")
    generator._client = fake_client  # type: ignore[assignment]

    captured: Dict[str, Any] = {}
    template = _build_template(captured)

    comment = "Tache visible sur la manche"
    generator.generate_listing(["data:image/png;base64,AAA"], comment, template, "")

    fields = captured.get("fields")
    assert fields is not None
    assert fields.defects == comment


def test_polaire_invalid_sku_fallbacks_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.backend.gpt_client.OpenAI", object)
    invalid_payload = _polaire_fields_payload(
        sku="PTNF-42",
        brand="Columbia",
        fabric_label_visible=True,
        non_size_labels_visible=True,
    )
    main_response = _listing_response(invalid_payload)
    fake_client = FakeClient([main_response])

    generator = ListingGenerator(model="fake", api_key="test")
    generator._client = fake_client  # type: ignore[assignment]

    captured: Dict[str, Any] = {}

    def _render(fields: ListingFields) -> tuple[str, str]:
        captured["fields"] = fields
        return ("TITLE", f"DESC-{fields.sku or 'EMPTY'}")

    template = ListingTemplate(
        name="template-polaire-outdoor",
        description="",
        prompt="PROMPT",
        render_callback=_render,
    )

    def _recover(self, _images: list[str], _comment: str) -> str:
        return ""

    monkeypatch.setattr(ListingGenerator, "_recover_polaire_sku", _recover, raising=True)

    result = generator.generate_listing(["data:image/png;base64,AAA"], "", template, "")

    assert result.title == "TITLE"
    assert result.sku_missing is True
    fields = captured.get("fields")
    assert fields is not None
    assert fields.sku == ""


def test_manual_polaire_sku_used_in_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.backend.gpt_client.OpenAI", object)
    payload = _polaire_fields_payload(
        sku="",
        brand="The North Face",
        fabric_label_visible=False,
        non_size_labels_visible=False,
    )
    main_response = _listing_response(payload)
    fake_client = FakeClient([main_response])

    generator = ListingGenerator(model="fake", api_key="test")
    generator._client = fake_client  # type: ignore[assignment]

    captured: Dict[str, Any] = {}

    def _render(fields: ListingFields) -> tuple[str, str]:
        captured["fields"] = fields
        return ("TITLE", f"DESC-{fields.sku or 'EMPTY'}")

    template = ListingTemplate(
        name="template-polaire-outdoor",
        description="",
        prompt="PROMPT",
        render_callback=_render,
    )

    def _recover(_self, _images: list[str], _comment: str) -> str:  # pragma: no cover - safety
        raise AssertionError("Targeted recovery should not run when SKU is provided manually")

    monkeypatch.setattr(ListingGenerator, "_recover_polaire_sku", _recover, raising=True)

    manual_sku = "PTNF 99"
    result = generator.generate_listing(
        ["data:image/png;base64,AAA"], "", template, "", manual_sku=manual_sku
    )

    assert result.description == "DESC-PTNF-99"
    assert result.sku_missing is False
    fields = captured.get("fields")
    assert fields is not None
    assert fields.sku == "PTNF-99"


def test_polaire_hallucinated_sku_cleared_when_brand_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.backend.gpt_client.OpenAI", object)
    payload = _polaire_fields_payload(
        sku="PTNF-77",
        brand="",  # marque non identifiée
        fabric_label_visible=True,
        non_size_labels_visible=True,
    )
    main_response = _listing_response(payload)
    fake_client = FakeClient([main_response])

    generator = ListingGenerator(model="fake", api_key="test")
    generator._client = fake_client  # type: ignore[assignment]

    captured: Dict[str, Any] = {"recover_called": False}

    def _recover(self, _images: list[str], _comment: str) -> str:
        captured["recover_called"] = True
        return ""

    monkeypatch.setattr(ListingGenerator, "_recover_polaire_sku", _recover, raising=True)

    template = ListingTemplate(
        name="template-polaire-outdoor",
        description="",
        prompt="PROMPT",
        render_callback=lambda fields: ("TITLE", f"DESC-{fields.sku or 'EMPTY'}"),
    )

    result = generator.generate_listing(["data:image/png;base64,AAA"], "", template, "")

    assert captured["recover_called"] is True
    assert result.sku_missing is True
    assert result.description == "DESC-EMPTY"


def test_polaire_sku_recovery_runs_when_fabric_label_cut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.backend.gpt_client.OpenAI", object)
    payload = _polaire_fields_payload(
        sku="PTNF-10",
        fabric_label_visible=True,
        non_size_labels_visible=True,
        fabric_label_cut=True,
    )
    main_response = _listing_response(payload)
    fake_client = FakeClient([main_response])

    generator = ListingGenerator(model="fake", api_key="test")
    generator._client = fake_client  # type: ignore[assignment]

    captured: Dict[str, Any] = {"recover_called": False}

    def _recover(self, _images: list[str], _comment: str) -> str:
        captured["recover_called"] = True
        return ""

    monkeypatch.setattr(ListingGenerator, "_recover_polaire_sku", _recover, raising=True)

    template = ListingTemplate(
        name="template-polaire-outdoor",
        description="",
        prompt="PROMPT",
        render_callback=lambda fields: ("TITLE", f"DESC-{fields.sku or 'EMPTY'}"),
    )

    result = generator.generate_listing(["data:image/png;base64,ZZZ"], "", template, "")

    assert captured["recover_called"] is True
    assert result.sku_missing is True
    assert result.description == "DESC-EMPTY"
