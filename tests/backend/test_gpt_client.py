"""Tests for the ListingGenerator Tommy SKU recovery."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.gpt_client import ListingGenerator
from app.backend.templates import ListingTemplate


@dataclass
class FakeResponse:
    output_text: str


class FakeResponses:
    def __init__(self, outputs: Sequence[FakeResponse]) -> None:
        self._outputs = list(outputs)
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        index = len(self.calls)
        self.calls.append(kwargs)
        if index >= len(self._outputs):
            raise AssertionError("Trop d'appels simulés à responses.create")
        return self._outputs[index]


class FakeClient:
    def __init__(self, outputs: Sequence[FakeResponse]) -> None:
        self.responses = FakeResponses(outputs)


def _base_fields_payload() -> Dict[str, Any]:
    return {
        "model": "Tommy 01",
        "fr_size": "M",
        "us_w": "",
        "us_l": "",
        "fit_leg": "",
        "rise_class": "",
        "rise_measurement_cm": "",
        "waist_measurement_cm": "",
        "cotton_pct": "80",
        "polyester_pct": "20",
        "polyamide_pct": "",
        "viscose_pct": "",
        "elastane_pct": "",
        "acrylic_pct": "",
        "gender": "Femme",
        "color_main": "Bleu",
        "defects": "",
        "sku": "",
        "defect_tags": [],
        "size_label_visible": True,
        "fabric_label_visible": True,
        "fabric_label_cut": False,
        "wool_pct": "",
        "cashmere_pct": "",
        "nylon_pct": "",
        "acrylic_pct": "",
        "knit_pattern": "",
        "made_in": "",
        "is_cardigan": False,
    }


@pytest.fixture
def tommy_template() -> ListingTemplate:
    calls: List[Any] = []

    def _render(fields: Any) -> Sequence[str]:
        calls.append(fields)
        return ("titre", "description")

    template = ListingTemplate(
        name="template-pull-tommy-femme",
        description="",
        prompt="",
        render_callback=_render,
    )
    template._render_calls = calls  # type: ignore[attr-defined]
    return template


def test_tommy_sku_recovery_success(tommy_template: ListingTemplate) -> None:
    payload = _base_fields_payload()
    first_response = FakeResponse(json.dumps({"fields": payload}))
    second_response = FakeResponse("PTF52")
    generator = ListingGenerator(model="stub", api_key="stub")
    generator._client = FakeClient([first_response, second_response])  # type: ignore[attr-defined]

    generator.generate_listing(["image://one"], "", tommy_template)

    render_calls = getattr(tommy_template, "_render_calls")
    assert render_calls, "Le template devrait avoir été rendu"
    fields = render_calls[0]
    assert fields.sku == "PTF52"
    client_calls = generator._client.responses.calls  # type: ignore[attr-defined]
    assert len(client_calls) == 2
    helper_prompt_text = json.dumps(client_calls[1])
    assert "PTF" in helper_prompt_text
    assert "Analyse ces photos" in helper_prompt_text


def test_tommy_sku_recovery_failure_raises(tommy_template: ListingTemplate) -> None:
    payload = _base_fields_payload()
    first_response = FakeResponse(json.dumps({"fields": payload}))
    second_response = FakeResponse("")
    generator = ListingGenerator(model="stub", api_key="stub")
    generator._client = FakeClient([first_response, second_response])  # type: ignore[attr-defined]

    with pytest.raises(ValueError) as excinfo:
        generator.generate_listing(["image://one"], "", tommy_template)

    assert "SKU lisible est obligatoire" in str(excinfo.value)
    client_calls = generator._client.responses.calls  # type: ignore[attr-defined]
    assert len(client_calls) == 2
