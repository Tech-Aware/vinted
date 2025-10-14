"""Structured representation of the fields required to render a listing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


FieldValue = Optional[str]


@dataclass
class ListingFields:
    """Structured data extracted from the model response."""

    model: FieldValue
    fr_size: FieldValue
    us_w: FieldValue
    us_l: FieldValue
    fit_leg: FieldValue
    rise_class: FieldValue
    cotton_pct: FieldValue
    elastane_pct: FieldValue
    gender: FieldValue
    color_main: FieldValue
    defects: FieldValue
    sku: FieldValue

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ListingFields":
        missing = [
            key
            for key in (
                "model",
                "fr_size",
                "us_w",
                "us_l",
                "fit_leg",
                "rise_class",
                "cotton_pct",
                "elastane_pct",
                "gender",
                "color_main",
                "defects",
                "sku",
            )
            if key not in data
        ]
        if missing:
            raise ValueError(f"Champs manquants dans la réponse JSON: {', '.join(missing)}")

        def normalize(value: Any) -> FieldValue:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, str):
                return value.strip()
            raise ValueError(f"Type de valeur inattendu pour un champ: {type(value)!r}")

        return cls(
            model=normalize(data.get("model")),
            fr_size=normalize(data.get("fr_size")),
            us_w=normalize(data.get("us_w")),
            us_l=normalize(data.get("us_l")),
            fit_leg=normalize(data.get("fit_leg")),
            rise_class=normalize(data.get("rise_class")),
            cotton_pct=normalize(data.get("cotton_pct")),
            elastane_pct=normalize(data.get("elastane_pct")),
            gender=normalize(data.get("gender")),
            color_main=normalize(data.get("color_main")),
            defects=normalize(data.get("defects")),
            sku=normalize(data.get("sku")),
        )

    @property
    def has_elastane(self) -> bool:
        value = (self.elastane_pct or "").strip()
        if not value:
            return False
        try:
            return float(value.strip("% ")) > 0
        except ValueError:
            return False

    @staticmethod
    def json_instruction() -> str:
        return (
            "Réponds EXCLUSIVEMENT avec un JSON valide contenant une clé 'fields' structurée comme suit :\n"
            "{\n"
            "  \"fields\": {\n"
            "    \"model\": \"nom du modèle Levi's (ex: 501)\",\n"
            "    \"fr_size\": \"taille française visible (ex: 38)\",\n"
            "    \"us_w\": \"largeur US W (ex: 28)\",\n"
            "    \"us_l\": \"longueur US L (ex: 30)\",\n"
            "    \"fit_leg\": \"coupe détectée (bootcut, straight, slim, skinny, etc.)\",\n"
            "    \"rise_class\": \"hauteur de taille (basse, moyenne, haute)\",\n"
            "    \"cotton_pct\": \"pourcentage de coton (ex: 99)\",\n"
            "    \"elastane_pct\": \"pourcentage d'élasthanne (0 si absent)\",\n"
            "    \"gender\": \"genre ciblé (femme, homme, mixte)\",\n"
            "    \"color_main\": \"couleur principale\",\n"
            "    \"defects\": \"défauts ou taches identifiés\",\n"
            "    \"sku\": \"référence interne\"\n"
            "  }\n"
            "}\n"
            "N'inclus aucun autre texte hors de ce JSON. Les valeurs doivent être au format chaîne.\n"
            "Indique la coupe en anglais dans 'fit_leg' (ex: bootcut, straight, slim)."
        )

