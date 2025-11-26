from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.customer_responses import (
    CustomerReplyGenerator,
    CustomerReplyPayload,
    SCENARIOS,
)


def test_negocier_plus_haut_prompt_omits_client_offer() -> None:
    scenario = SCENARIOS["negocier_plus_haut"]
    payload = CustomerReplyPayload(
        client_name="Alice",
        article_type="jacket",
        scenario_id=scenario.id,
        client_message="Bonjour !",
        offre_client=10,
        contre_offre=15,
    )

    generator = CustomerReplyGenerator(model="test")
    prompt = generator._build_prompt(payload, scenario)

    assert "Offre client" not in prompt
    assert "Votre proposition" not in prompt
    assert scenario.label in prompt


def test_negocier_prix_ferme_keeps_price_context() -> None:
    scenario = SCENARIOS["negocier_prix_ferme"]
    payload = CustomerReplyPayload(
        client_name="Bob",
        article_type="jean_levis",
        scenario_id=scenario.id,
        client_message="Pouvez-vous baisser le prix ?",
        offre_client=12,
        prix_ferme=18,
    )

    generator = CustomerReplyGenerator(model="test")
    prompt = generator._build_prompt(payload, scenario)

    assert "Offre client: 12€" in prompt
    assert "Prix ferme: 18€" in prompt
    assert scenario.label in prompt
