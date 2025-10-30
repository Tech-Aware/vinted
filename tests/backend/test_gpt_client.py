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

    result = generator.generate_listing(["data:image/png;base64,AAA"], "", template)

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
        generator.generate_listing(["data:image/png;base64,BBB"], "", template)

    assert len(fake_client.responses.calls) == 2
