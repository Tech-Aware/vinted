from __future__ import annotations

from pathlib import Path

import pytest

from app.backend.templates import ListingTemplateRegistry
from app.ui.listing_app import generate_listing_with_auto_template


class DummyGenerator:
    def __init__(self) -> None:
        self.called_template_name: str | None = None

    def generate_listing(self, encoded_images, comment, template):  # type: ignore[override]
        self.called_template_name = template.name
        return {
            "images": encoded_images,
            "comment": comment,
            "template": template.name,
        }


def test_generate_listing_with_auto_template_selects_levis(
    monkeypatch: pytest.MonkeyPatch,
    simulated_levis_encoded_images,
) -> None:
    registry = ListingTemplateRegistry()
    generator = DummyGenerator()

    monkeypatch.setattr(
        "app.ui.listing_app.encode_images_to_base64",
        lambda paths: simulated_levis_encoded_images,
    )

    result, resolved = generate_listing_with_auto_template(
        "auto",
        [Path("fake1.jpg")],
        "Jean Levi's 501 délavé",
        registry,
        generator,
    )

    assert generator.called_template_name == "template-jean-levis-femme"
    assert resolved == "template-jean-levis-femme"
    assert result["template"] == "template-jean-levis-femme"


def test_generate_listing_with_auto_template_selects_tommy(
    monkeypatch: pytest.MonkeyPatch,
    simulated_tommy_encoded_images,
) -> None:
    registry = ListingTemplateRegistry()
    generator = DummyGenerator()

    monkeypatch.setattr(
        "app.ui.listing_app.encode_images_to_base64",
        lambda paths: simulated_tommy_encoded_images,
    )

    result, resolved = generate_listing_with_auto_template(
        "auto",
        [Path("fake2.jpg")],
        "Pull Tommy Hilfiger marinière",
        registry,
        generator,
    )

    assert generator.called_template_name == "template-pull-tommy-femme"
    assert resolved == "template-pull-tommy-femme"
    assert result["template"] == "template-pull-tommy-femme"


def test_generate_listing_with_auto_template_propagates_error(
    monkeypatch: pytest.MonkeyPatch,
    simulated_uncertain_images,
) -> None:
    registry = ListingTemplateRegistry()
    generator = DummyGenerator()

    monkeypatch.setattr(
        "app.ui.listing_app.encode_images_to_base64",
        lambda paths: simulated_uncertain_images,
    )

    with pytest.raises(Exception) as excinfo:
        generate_listing_with_auto_template(
            "auto",
            [Path("fake3.jpg")],
            "",  # no hint
            registry,
            generator,
        )

    assert "incertaine" in str(excinfo.value)

