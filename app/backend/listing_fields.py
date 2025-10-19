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
from textwrap import dedent
from typing import Any, Mapping, Optional

from app.backend.defect_catalog import iter_prompt_defects, known_defect_slugs
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
        defect_tags = ListingFields._augment_defect_tags_from_text(defects, defect_tags)

        size_label_visible = ListingFields._normalize_visibility_flag(
            data.get("size_label_visible"), default=False
        )
        fabric_label_visible = ListingFields._normalize_visibility_flag(
            data.get("fabric_label_visible"), default=False
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
        if not self.fabric_label_visible:
            return False
        value = (self.elastane_pct or "").strip()
        if not value:
            return False
        try:
            return float(value.strip("% ")) > 0
        except ValueError:
            return False

    @property
    def has_polyester(self) -> bool:
        if not self.fabric_label_visible:
            return False
        value = (self.polyester_pct or "").strip()
        if not value:
            return False
        try:
            return float(value.strip("% ")) > 0
        except ValueError:
            return False

    @staticmethod
    def json_instruction() -> str:
        slugs = ', '.join(known_defect_slugs()) or 'aucun'
        defect_lines = []
        for spec in iter_prompt_defects():
            synonyms = ', '.join(spec.synonyms)
            if synonyms:
                defect_lines.append(
                    f"- `{spec.slug}` : {spec.description} (synonymes : {synonyms})"
                )
            else:
                defect_lines.append(f"- `{spec.slug}` : {spec.description}")

        defect_help = "".join(["Défauts disponibles :\n", *[line + "\n" for line in defect_lines]])

        instruction = dedent(
            f"""
            Réponds EXCLUSIVEMENT avec un JSON valide contenant une clé 'fields' structurée comme suit :
            {{
              \"fields\": {{
                \"model\": \"code numérique du modèle Levi's (ex: 501) avec le suffixe 'Premium' uniquement si indiqué ; renvoie \"\" si le code n'est pas parfaitement lisible\",
                \"fr_size\": \"taille française lisible (ex: 38) ; renvoie \"\" si aucune taille fiable n'est visible\",
                \"us_w\": \"largeur US W lisible (ex: 28) ; renvoie \"\" si non lisible\",
                \"us_l\": \"longueur US L lisible (ex: 30) ; renvoie \"\" si non lisible\",
                \"fit_leg\": \"coupe détectée (bootcut, straight, slim, skinny, etc.) ; renvoie \"\" si la coupe n'est pas certaine\",
                \"rise_class\": \"hauteur de taille (basse, moyenne, haute) ; renvoie \"\" si non confirmée\",
                \"cotton_pct\": \"pourcentage de coton indiqué sur l'étiquette ; renvoie \"\" si l'information n'est pas lisible\",
                \"polyester_pct\": \"pourcentage de polyester indiqué ; renvoie \"\" si absent ou illisible\",
                \"elastane_pct\": \"pourcentage d'élasthanne indiqué ; renvoie \"\" si absent ou illisible\",
                \"gender\": \"genre ciblé (femme, homme, mixte) uniquement s'il est explicitement mentionné ; sinon renvoie \"\"\",
                \"color_main\": \"couleur principale visible ; renvoie \"\" si la couleur n'est pas évidente\",
                \"defects\": \"défauts ou taches identifiés ; renvoie \"\" s'il n'y en a pas ou qu'ils ne sont pas visibles\",
                \"defect_tags\": \"liste de slugs parmi [{slugs}] à renseigner UNIQUEMENT si le défaut est visible sur les photos\",
                \"size_label_visible\": \"true/false : true uniquement si une étiquette de taille est réellement lisible\",
                \"fabric_label_visible\": \"true/false : true uniquement si une étiquette de composition est réellement lisible\",
                \"sku\": \"SKU Levi's : JLF + numéro (1-3 chiffres) pour un jean femme, JLH + numéro (1-3 chiffres) pour un jean homme ; renvoie \"\" si l'étiquette n'est pas lisible\"
              }}
            }}
            N'inclus aucun autre texte hors de ce JSON. Les valeurs doivent être au format chaîne, sauf les booléens qui doivent être true/false.
            Indique la coupe en anglais dans 'fit_leg' (ex: bootcut, straight, slim).
            Ne remplis jamais un champ avec une valeur estimée ou supposée ; retourne la chaîne vide quand une information est manquante ou incertaine.
            Renseigne size_label_visible et fabric_label_visible à false par défaut et ne les mets à true que si l'étiquette correspondante est parfaitement lisible.
            """
        ).strip()

        if defect_lines:
            instruction = f"{defect_help.strip()}\n\n{instruction}"

        return instruction

    @staticmethod
    def _normalize_defect_tags(raw_tags: Any) -> Sequence[str]:
        if raw_tags is None:
            return ()
        if isinstance(raw_tags, str):
            # Les modèles ont tendance à renvoyer une chaîne unique contenant
            # plusieurs slugs séparés par des virgules. On découpe donc la
            # chaîne afin de valider chaque slug individuellement.
            split_tags = [part for part in re.split(r"[,;\n]+", raw_tags) if part]
            raw_iterable: Iterable[Any] = split_tags or [raw_tags]
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
    def _augment_defect_tags_from_text(
        defects: FieldValue, defect_tags: Sequence[str]
    ) -> Sequence[str]:
        if not defects:
            return defect_tags

        normalized_text = defects.lower()
        if not normalized_text:
            return defect_tags

        existing = list(defect_tags)
        seen = set(defect_tags)

        # Iterate over prompt defect order to keep deterministic output.
        for spec in iter_prompt_defects():
            slug = spec.slug
            if slug in seen:
                continue
            for synonym in spec.synonyms:
                normalized_synonym = synonym.lower().strip()
                if normalized_synonym and normalized_synonym in normalized_text:
                    existing.append(slug)
                    seen.add(slug)
                    break
            else:
                normalized_description = (spec.description or "").lower().strip()
                if (
                    normalized_description
                    and slug not in seen
                    and normalized_description in normalized_text
                ):
                    existing.append(slug)
                    seen.add(slug)

        return tuple(existing)

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

