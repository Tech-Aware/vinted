"""Integration tests for user overrides in listing generation."""

from app.backend.gpt_client import ListingGenerator
from app.backend.templates import ListingTemplateRegistry
from app.backend.listing_fields import ListingFields


def test_apply_user_overrides_propagates_fr_size_to_render() -> None:
    generator = ListingGenerator(model="fake", api_key="test")
    template = ListingTemplateRegistry().get_template("template-jean-levis-femme")

    fields = ListingFields(
        model="501",
        fr_size="38",
        us_w="28",
        us_l="32",
        fit_leg="straight",
        rise_class="regular",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="100",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="Femme",
        color_main="bleu",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="JLF123",
    )

    comment = "Merci ! Taille FR40, vérifier la couleur bleu"

    overridden_fields = generator._apply_user_overrides(comment, fields)

    assert overridden_fields.fr_size == "40"

    title, description, price_estimate = template.render(overridden_fields)

    assert "FR40" in title
    assert "40 FR" in description
    assert price_estimate is not None
    assert "FR 40" in price_estimate


def test_apply_user_overrides_preserves_us_size_when_explicit() -> None:
    generator = ListingGenerator(model="fake", api_key="test")
    template = ListingTemplateRegistry().get_template("template-jean-levis-femme")

    fields = ListingFields(
        model="501",
        fr_size="38",
        us_w="30",
        us_l="32",
        fit_leg="straight",
        rise_class="regular",
        rise_measurement_cm=None,
        waist_measurement_cm=None,
        cotton_pct="100",
        polyester_pct="",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="Femme",
        color_main="bleu",
        defects="",
        defect_tags=(),
        size_label_visible=True,
        fabric_label_visible=True,
        sku="JLF123",
    )

    comment = "Taille FR40 (us w30 l32), merci !"

    overridden_fields = generator._apply_user_overrides(comment, fields)

    assert overridden_fields.fr_size == "40"
    assert overridden_fields.us_w == "30"
    assert overridden_fields.us_l == "32"

    title, description, _ = template.render(overridden_fields)

    assert "W30" in title
    assert "L32" in title
    assert "30 US (équivalent 40 FR)" in description


def test_apply_user_overrides_strips_sizes_when_label_missing() -> None:
    generator = ListingGenerator(model="fake", api_key="test")

    fields = ListingFields(
        model="511",
        fr_size="38",
        us_w="29",
        us_l="32",
        fit_leg="slim",
        rise_class="mid",
        rise_measurement_cm=None,
        waist_measurement_cm=72.0,
        cotton_pct="99",
        polyester_pct="1",
        polyamide_pct="",
        viscose_pct="",
        elastane_pct="",
        gender="Homme",
        color_main="bleu foncé",
        defects="",
        defect_tags=(),
        size_label_visible=False,
        fabric_label_visible=False,
        sku="JLF5",
    )

    sanitized_fields = generator._apply_user_overrides("", fields)

    assert sanitized_fields.fr_size == ""
    assert sanitized_fields.us_w == ""
    assert sanitized_fields.us_l == ""
    assert sanitized_fields.waist_measurement_cm == 72.0
