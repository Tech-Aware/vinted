from app.backend.template_classifier import (
    TemplateClassificationError,
    infer_template,
)


def test_infer_template_detects_levis(simulated_levis_encoded_images) -> None:
    result = infer_template(simulated_levis_encoded_images, "Jean Levi's 501")
    assert result == "template-jean-levis-femme"


def test_infer_template_detects_tommy(simulated_tommy_encoded_images) -> None:
    result = infer_template(simulated_tommy_encoded_images, "Pull Tommy Hilfiger rayé")
    assert result == "template-pull-tommy-femme"


def test_infer_template_requires_confidence(simulated_uncertain_images) -> None:
    try:
        infer_template(simulated_uncertain_images, "")
    except TemplateClassificationError as exc:
        assert "incertaine" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected classification error")

