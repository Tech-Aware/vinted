from __future__ import annotations

"""
Copyright 2025 Kevin Andreazza
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy at http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""Structured representation of the fields required to render a listing."""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from app.backend.defect_catalog import known_defect_slugs
from app.backend.text_normalization import normalize_model_code


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
    polyester_pct: FieldValue
    elastane_pct: FieldValue
    gender: FieldValue
    color_main: FieldValue
    defects: FieldValue
    defect_tags: Sequence[str]
    size_label_visible: bool
    fabric_label_visible: bool
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
                "polyester_pct",
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

        model = normalize(data.get("model"))
        fr_size = normalize(data.get("fr_size"))
        us_w = normalize(data.get("us_w"))
        us_l = normalize(data.get("us_l"))
        fit_leg = normalize(data.get("fit_leg"))
        rise_class = normalize(data.get("rise_class"))
        cotton_pct = normalize(data.get("cotton_pct"))
        polyester_pct = normalize(data.get("polyester_pct"))
        elastane_pct = normalize(data.get("elastane_pct"))
        gender = normalize(data.get("gender"))
        color_main = normalize(data.get("color_main"))
        defects = normalize(data.get("defects"))
        sku_raw = normalize(data.get("sku"))

        defect_tags_raw = data.get("defect_tags", [])
        defect_tags: Sequence[str] = ListingFields._normalize_defect_tags(defect_tags_raw)

        size_label_visible = ListingFields._normalize_visibility_flag(
            data.get("size_label_visible"), default=True
        )
        fabric_label_visible = ListingFields._normalize_visibility_flag(
            data.get("fabric_label_visible"), default=True
        )
        sku = sku_raw.upper() if sku_raw else sku_raw

        if sku:
            gender_normalized = (gender or "").lower()
            if "homme" in gender_normalized:
                pattern = r"^JLH\d{1,3}$"
            elif "femme" in gender_normalized:
                pattern = r"^JLF\d{1,3}$"
            else:
                pattern = r"^JL[HF]\d{1,3}$"

            if not re.fullmatch(pattern, sku):
                raise ValueError(
                    "SKU invalide: il doit suivre le format JLF/JLH + numéro (1 à 3 chiffres)"
                    " correspondant au genre détecté."
                )

        return cls(
            model=normalize_model_code(model),
            fr_size=fr_size,
            us_w=us_w,
            us_l=us_l,
            fit_leg=fit_leg,
            rise_class=rise_class,
            cotton_pct=cotton_pct,
            polyester_pct=polyester_pct,
            elastane_pct=elastane_pct,
            gender=gender,
            color_main=color_main,
            defects=defects,
            defect_tags=defect_tags,
            size_label_visible=size_label_visible,
            fabric_label_visible=fabric_label_visible,
            sku=sku,
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

    @property
    def has_polyester(self) -> bool:
        value = (self.polyester_pct or "").strip()
        if not value:
            return False
        try:
            return float(value.strip("% ")) > 0
        except ValueError:
            return False

    @staticmethod
    def json_instruction() -> str:
        slugs = ", ".join(known_defect_slugs()) or "aucun"
        return (
            "Réponds EXCLUSIVEMENT avec un JSON valide contenant une clé 'fields' structurée comme suit :\n"
            "{\n"
            "  \"fields\": {\n"
            "    \"model\": \"code numérique du modèle Levi's (ex: 501) avec le suffixe 'Premium' uniquement si indiqué ; laisse ce champ vide si le code n'est pas visible ou confirmé sur les photos\",\n"
            "    \"fr_size\": \"taille française visible (ex: 38)\",\n"
            "    \"us_w\": \"largeur US W (ex: 28)\",\n"
            "    \"us_l\": \"longueur US L (ex: 30)\",\n"
            "    \"fit_leg\": \"coupe détectée (bootcut, straight, slim, skinny, etc.)\",\n"
            "    \"rise_class\": \"hauteur de taille (basse, moyenne, haute)\",\n"
            "    \"cotton_pct\": \"pourcentage de coton (ex: 99)\",\n"
            "    \"polyester_pct\": \"pourcentage de polyester (0 s'il est absent)\",\n"
            "    \"elastane_pct\": \"pourcentage d'élasthanne (0 si absent)\",\n"
            "    \"gender\": \"genre ciblé (femme, homme, mixte)\",\n"
            "    \"color_main\": \"couleur principale\",\n"
            "    \"defects\": \"défauts ou taches identifiés\",\n"
            f"    \"defect_tags\": \"liste de slugs parmi [{slugs}] à renseigner UNIQUEMENT si le défaut est visible sur les photos, même légèrement\",\n"
            "    \"size_label_visible\": \"true/false : indique si une étiquette de taille est lisible sur les photos\",\n"
            "    \"fabric_label_visible\": \"true/false : indique si une étiquette de composition est lisible sur les photos\",\n"
            "    \"sku\": \"SKU Levi's : JLF + numéro (1-3 chiffres) pour un jean femme,"
            " JLH + numéro (1-3 chiffres) pour un jean homme ; utilise le numéro de l'étiquette blanche\"\n"
            "  }\n"
            "}\n"
            "N'inclus aucun autre texte hors de ce JSON. Les valeurs doivent être au format chaîne, sauf les booléens qui doivent être true/false.\n"
            "Indique la coupe en anglais dans 'fit_leg' (ex: bootcut, straight, slim).\n"
            "Renseigne size_label_visible et fabric_label_visible à false dès qu'aucune étiquette lisible n'est visible sur les photos."
        )

    @staticmethod
    def _normalize_defect_tags(raw_tags: Any) -> Sequence[str]:
        if raw_tags is None:
            return ()
        if isinstance(raw_tags, str):
            raw_iterable: Iterable[Any] = [raw_tags]
        elif isinstance(raw_tags, Iterable) and not isinstance(raw_tags, (bytes, bytearray)):
            raw_iterable = raw_tags
        else:
            raise ValueError("'defect_tags' doit être une liste de slugs")

        slugs = []
        valid_slugs = set(known_defect_slugs())
        for item in raw_iterable:
            if not isinstance(item, str):
                raise ValueError("Chaque élément de 'defect_tags' doit être une chaîne")
            slug = item.strip()
            if not slug:
                continue
            if slug not in valid_slugs:
                raise ValueError(f"Slug de défaut inconnu: {slug}")
            slugs.append(slug)
        return tuple(slugs)

    @staticmethod
    def _normalize_visibility_flag(value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if value in (0, 1):
                return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "vrai", "1"}:
                return True
            if lowered in {"false", "faux", "0"}:
                return False
        raise ValueError("Les indicateurs d'étiquette doivent être des booléens")

