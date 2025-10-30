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
import unicodedata

from app.backend.defect_catalog import iter_prompt_defects, known_defect_slugs
from app.backend.text_normalization import normalize_model_code


FieldValue = Optional[str]


def _normalize_text(value: str) -> str:
    """Normalize text for accent-insensitive comparisons."""

    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()


_EUROPE_KEYWORDS = (
    "made in europe",
    "fabrique en europe",
    "fabriqué en europe",
    "fabrication europeenne",
    "fabrication européenne",
    "made in eu",
    "fabrique dans l'union europeenne",
    "fabriqué dans l'union européenne",
    "union europeenne",
    "union européenne",
)


_EUROPE_COUNTRY_KEYWORDS = (
    "allemagne",
    "autriche",
    "belgique",
    "bulgarie",
    "croatie",
    "chypre",
    "danemark",
    "espagne",
    "estonie",
    "finlande",
    "france",
    "grece",
    "grèce",
    "hongrie",
    "irlande",
    "italie",
    "lettonie",
    "lituanie",
    "luxembourg",
    "malte",
    "pays-bas",
    "pologne",
    "portugal",
    "republique tcheque",
    "république tchèque",
    "roumanie",
    "slovaquie",
    "slovenie",
    "slovénie",
    "suede",
    "suède",
    "suisse",
    "royaume-uni",
    "germany",
    "austria",
    "belgium",
    "bulgaria",
    "croatia",
    "cyprus",
    "czech republic",
    "denmark",
    "spain",
    "estonia",
    "finland",
    "france",
    "greece",
    "hungary",
    "ireland",
    "italy",
    "latvia",
    "lithuania",
    "luxembourg",
    "malta",
    "netherlands",
    "poland",
    "portugal",
    "romania",
    "slovakia",
    "slovenia",
    "sweden",
    "switzerland",
    "united kingdom",
)


@dataclass
class ListingFields:
    """Structured data extracted from the model response."""

    model: FieldValue
    fr_size: FieldValue
    us_w: FieldValue
    us_l: FieldValue
    fit_leg: FieldValue
    rise_class: FieldValue
    rise_measurement_cm: Optional[float]
    waist_measurement_cm: Optional[float]
    cotton_pct: FieldValue
    polyester_pct: FieldValue
    polyamide_pct: FieldValue
    viscose_pct: FieldValue
    elastane_pct: FieldValue
    gender: FieldValue
    color_main: FieldValue
    defects: FieldValue
    defect_tags: Sequence[str]
    size_label_visible: bool
    fabric_label_visible: bool
    sku: FieldValue
    fabric_label_cut: bool = False
    is_cardigan: bool = False
    wool_pct: FieldValue = None
    cashmere_pct: FieldValue = None
    nylon_pct: FieldValue = None
    acrylic_pct: FieldValue = None
    knit_pattern: FieldValue = None
    made_in: FieldValue = None

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, template_name: Optional[str] = None
    ) -> "ListingFields":
        missing = [
            key
            for key in (
                "model",
                "fr_size",
                "us_w",
                "us_l",
                "fit_leg",
                "rise_class",
                "rise_measurement_cm",
                "waist_measurement_cm",
                "cotton_pct",
                "polyester_pct",
                "polyamide_pct",
                "viscose_pct",
                "elastane_pct",
                "acrylic_pct",
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
        rise_measurement_cm = ListingFields._parse_rise_measurement(
            data.get("rise_measurement_cm")
        )
        waist_measurement_cm = ListingFields._parse_waist_measurement(
            data.get("waist_measurement_cm")
        )
        cotton_pct = normalize(data.get("cotton_pct"))
        polyester_pct = normalize(data.get("polyester_pct"))
        viscose_pct = normalize(data.get("viscose_pct"))
        elastane_pct = normalize(data.get("elastane_pct"))
        polyamide_pct = normalize(data.get("polyamide_pct"))
        nylon_pct = normalize(data.get("nylon_pct"))
        acrylic_pct = normalize(data.get("acrylic_pct"))
        gender = normalize(data.get("gender"))
        color_main = normalize(data.get("color_main"))
        defects = normalize(data.get("defects"))
        wool_pct = normalize(data.get("wool_pct"))
        cashmere_pct = normalize(data.get("cashmere_pct"))
        knit_pattern = normalize(data.get("knit_pattern"))
        made_in = normalize(data.get("made_in"))
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
        fabric_label_cut = ListingFields._normalize_visibility_flag(
            data.get("fabric_label_cut"), default=False
        )
        sku = sku_raw.upper() if sku_raw else sku_raw
        is_cardigan = ListingFields._normalize_visibility_flag(
            data.get("is_cardigan"), default=False
        )

        if sku:
            gender_normalized = (gender or "").lower()
            template_normalized = (template_name or "").strip().lower()
            allowed_patterns: list[str] = []

            if template_normalized == "template-pull-tommy-femme":
                allowed_patterns.append(r"^PTF\d{1,3}$")
            else:
                if "homme" in gender_normalized:
                    allowed_patterns.append(r"^JLH\d{1,3}$")
                elif "femme" in gender_normalized:
                    allowed_patterns.append(r"^JLF\d{1,3}$")
                else:
                    allowed_patterns.extend([r"^JLH\d{1,3}$", r"^JLF\d{1,3}$"])

            if not allowed_patterns:
                allowed_patterns.extend([r"^JLH\d{1,3}$", r"^JLF\d{1,3}$"])

            if not any(re.fullmatch(pattern, sku) for pattern in allowed_patterns):
                if template_normalized == "template-pull-tommy-femme":
                    raise ValueError(
                        "SKU invalide: utilise le préfixe PTF suivi de 1 à 3 chiffres pour le template Pull Tommy femme."
                    )
                raise ValueError(
                    "SKU invalide: utilise un préfixe Levi's autorisé (JLF ou JLH) correspondant au genre détecté."
                )

        return cls(
            model=normalize_model_code(model),
            fr_size=fr_size,
            us_w=us_w,
            us_l=us_l,
            fit_leg=fit_leg,
            rise_class=rise_class,
            rise_measurement_cm=rise_measurement_cm,
            waist_measurement_cm=waist_measurement_cm,
            cotton_pct=cotton_pct,
            polyester_pct=polyester_pct,
            polyamide_pct=polyamide_pct,
            viscose_pct=viscose_pct,
            elastane_pct=elastane_pct,
            nylon_pct=nylon_pct,
            acrylic_pct=acrylic_pct,
            gender=gender,
            color_main=color_main,
            defects=defects,
            defect_tags=defect_tags,
            size_label_visible=size_label_visible,
            fabric_label_visible=fabric_label_visible,
            fabric_label_cut=fabric_label_cut,
            sku=sku,
            wool_pct=wool_pct,
            cashmere_pct=cashmere_pct,
            knit_pattern=knit_pattern,
            made_in=made_in,
            is_cardigan=is_cardigan,
        )

    @staticmethod
    def _parse_measurement(value: Any, *, field_name: str) -> Optional[float]:
        """Convert raw measurement input to a float in centimeters."""

        if value is None:
            return None
        if isinstance(value, (int, float)):
            numeric = float(value)
        elif isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            lowered = stripped.lower()
            for variant in ("centimètres", "centimetres", "centimeter", "centimeters"):
                lowered = lowered.replace(variant, "cm")
            for space in ("\u202f", "\u00a0"):
                lowered = lowered.replace(space, " ")
            match = re.search(r"(\d+(?:[\s]*\d)*)(?:[.,]\s*(\d+))?", lowered)
            if not match:
                return None
            integer_part = match.group(1).replace(" ", "")
            decimal_part = match.group(2) or ""
            number_str = integer_part
            if decimal_part:
                number_str = f"{integer_part}.{decimal_part}"
            try:
                numeric = float(number_str)
            except ValueError:
                return None
        else:
            raise ValueError(f"'{field_name}' doit être une chaîne ou un nombre")

        if numeric <= 0:
            return None
        return numeric

    @staticmethod
    def _parse_rise_measurement(value: Any) -> Optional[float]:
        return ListingFields._parse_measurement(value, field_name="rise_measurement_cm")

    @staticmethod
    def _parse_waist_measurement(value: Any) -> Optional[float]:
        return ListingFields._parse_measurement(value, field_name="waist_measurement_cm")

    @staticmethod
    def _percentage_to_float(value: FieldValue) -> Optional[float]:
        if not value:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        stripped = stripped.replace("%", "").replace(",", ".")
        try:
            return float(stripped)
        except ValueError:
            return None

    @property
    def resolved_rise_class(self) -> str:
        """Return the best effort rise class, falling back to the measurement when available."""

        explicit_value = (self.rise_class or "").strip()
        if explicit_value:
            return explicit_value

        measurement = self.rise_measurement_cm
        if measurement is None:
            return ""

        if 18 <= measurement <= 22:
            return "basse"
        if 23 <= measurement <= 27:
            return "moyenne"
        if 28 <= measurement <= 33:
            return "haute"
        if measurement >= 34:
            return "très haute"
        return ""

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

    @property
    def has_viscose(self) -> bool:
        if not self.fabric_label_visible:
            return False
        value = (self.viscose_pct or "").strip()
        if not value:
            return False
        try:
            return float(value.strip("% ")) > 0
        except ValueError:
            return False

    @property
    def has_polyamide(self) -> bool:
        if not self.fabric_label_visible:
            return False
        value = self._percentage_to_float(self.polyamide_pct)
        return value is not None and value > 0

    @property
    def has_wool(self) -> bool:
        if not self.fabric_label_visible:
            return False
        value = self._percentage_to_float(self.wool_pct)
        return value is not None and value > 0

    @property
    def has_cashmere(self) -> bool:
        if not self.fabric_label_visible:
            return False
        value = self._percentage_to_float(self.cashmere_pct)
        return value is not None and value > 0

    @property
    def has_nylon(self) -> bool:
        if not self.fabric_label_visible:
            return False
        value = self._percentage_to_float(self.nylon_pct)
        return value is not None and value > 0

    @property
    def has_acrylic(self) -> bool:
        if not self.fabric_label_visible:
            return False
        value = self._percentage_to_float(self.acrylic_pct)
        return value is not None and value > 0

    @property
    def cotton_percentage_value(self) -> Optional[float]:
        return self._percentage_to_float(self.cotton_pct)

    @property
    def is_pure_cotton(self) -> bool:
        """Return True when the visible fabric label states 100% cotton only."""

        if not self.fabric_label_visible:
            return False

        cotton_value = self.cotton_percentage_value
        if cotton_value is None:
            return False

        if cotton_value < 99.5:
            return False

        return not any(
            (
                self.has_wool,
                self.has_cashmere,
                self.has_viscose,
                self.has_polyester,
                self.has_polyamide,
                self.has_nylon,
                self.has_elastane,
                self.has_acrylic,
            )
        )

    @property
    def wool_percentage_value(self) -> Optional[float]:
        return self._percentage_to_float(self.wool_pct)

    @property
    def cashmere_percentage_value(self) -> Optional[float]:
        return self._percentage_to_float(self.cashmere_pct)

    @property
    def made_in_europe(self) -> bool:
        if not self.made_in:
            return False
        normalized = _normalize_text(self.made_in)
        for keyword in _EUROPE_KEYWORDS:
            if _normalize_text(keyword) in normalized:
                return True
        for country in _EUROPE_COUNTRY_KEYWORDS:
            if _normalize_text(country) in normalized:
                return True
        return False

    @staticmethod
    def json_instruction(template_name: Optional[str] = None) -> str:
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

        if template_name == "template-pull-tommy-femme":
            instruction = dedent(
                f"""
                Réponds EXCLUSIVEMENT avec un JSON valide contenant une clé 'fields' structurée comme suit :
                {{
                  \"fields\": {{
                    \"model\": \"code produit lisible si présent ; renvoie \"\" si l'information n'est pas certaine\",
                    \"fr_size\": \"taille affichée (XS, S, M, etc.) ; renvoie \"\" si non lisible\",
                    \"us_w\": \"laisse ce champ vide pour les pulls (renvoie \"\")\",
                    \"us_l\": \"laisse ce champ vide pour les pulls (renvoie \"\")\",
                    \"fit_leg\": \"laisse ce champ vide pour les pulls (renvoie \"\")\",
                    \"rise_class\": \"laisse ce champ vide pour les pulls (renvoie \"\")\",
                    \"rise_measurement_cm\": \"laisse ce champ vide pour les pulls (renvoie \"\")\",
                    \"waist_measurement_cm\": \"laisse ce champ vide sauf si une mesure précise apparaît clairement\",
                    \"cotton_pct\": \"pourcentage de coton indiqué ; renvoie \"\" si absent ou illisible\",
                    \"wool_pct\": \"pourcentage de laine indiqué ; renvoie \"\" si absent ou illisible\",
                    \"cashmere_pct\": \"pourcentage de cachemire indiqué ; renvoie \"\" si absent ou illisible\",
                    \"polyester_pct\": \"pourcentage de polyester indiqué ; renvoie \"\" si absent ou illisible\",
                    \"polyamide_pct\": \"pourcentage de polyamide indiqué ; renvoie \"\" si absent ou illisible\",
                    \"viscose_pct\": \"pourcentage de viscose indiqué ; renvoie \"\" si absent ou illisible\",
                    \"elastane_pct\": \"pourcentage d'élasthanne indiqué ; renvoie \"\" si absent ou illisible\",
                    \"nylon_pct\": \"pourcentage de nylon indiqué ; renvoie \"\" si absent ou illisible\",
                    \"acrylic_pct\": \"pourcentage d'acrylique indiqué ; renvoie \"\" si absent ou illisible\",
                    \"gender\": \"genre ciblé (précise 'Femme' seulement si l'information est sûre) ; sinon renvoie \"\"\",
                    \"color_main\": \"couleurs principales visibles ; renvoie \"\" si la couleur n'est pas évidente\",
                    \"knit_pattern\": \"motif ou texture visible (marinière, torsadé, col V, etc.) ; renvoie \"\" si aucun détail fiable\",
                    \"made_in\": \"mention exacte du lieu de fabrication (ex: Made in Portugal) ; renvoie \"\" si non lisible\",
                    \"defects\": \"défauts ou taches identifiés ; renvoie \"\" s'il n'y en a pas\",
                    \"defect_tags\": \"liste de slugs parmi [{slugs}] à renseigner UNIQUEMENT si le défaut est visible sur les photos\",
                    \"size_label_visible\": \"true/false : true uniquement si l'étiquette de taille est parfaitement lisible\",
                    \"fabric_label_visible\": \"true/false : true uniquement si l'étiquette de composition est parfaitement lisible\",
                    \"fabric_label_cut\": \"true/false : true si l'étiquette matière a été coupée volontairement pour plus de confort ; false sinon\",
                    \"sku\": \"SKU Pull Tommy Femme : PTF + numéro (1-3 chiffres) lorsque l'étiquette est lisible ; renvoie \"\" sinon (ne jamais inventer, le rendu affichera 'SKU/nc'). Ce champ est obligatoire dès que l'étiquette est lisible : son omission fera échouer la génération\",
                    \"is_cardigan\": \"true/false : true si l'article est un gilet (avec ouverture complète) ; false sinon\"
                  }}
                }}
                N'inclus aucun autre texte hors de ce JSON. Les valeurs doivent être au format chaîne, sauf les booléens qui doivent être true/false.
                Ne remplis jamais un champ avec une valeur estimée ou supposée ; retourne la chaîne vide quand une information est manquante ou incertaine.
                N'invente jamais de matière : si une fibre n'est pas clairement indiquée ou que la ligne est illisible, renvoie la chaîne vide pour ce champ.
                Renseigne size_label_visible et fabric_label_visible à false par défaut et ne les mets à true que si l'étiquette correspondante est parfaitement lisible.
                Mentionne « Made in Europe » uniquement si l'étiquette confirme un pays européen et n'invente jamais de provenance.
                Dans le titre, supprime les pourcentages de laine ou de cachemire lorsqu'ils sont faibles, mais conserve la valeur numérique exacte dans la description et recopie-la dans les champs 'wool_pct' et 'cashmere_pct' dès que l'étiquette est lisible ; écris simplement « coton » si le pourcentage de coton est inférieur à 60%.
                """
            ).strip()
        else:
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
                    \"rise_class\": \"hauteur de taille (basse, moyenne, haute, très haute) ; renvoie \"\" si non confirmée\",
                    \"rise_measurement_cm\": \"mesure en cm entre le haut de la ceinture et l'entrejambe lorsque visible ; sinon renvoie \"\"\",
                    \"waist_measurement_cm\": \"tour de taille mesuré en cm lorsque visible ; sinon renvoie \"\"\",
                    \"cotton_pct\": \"pourcentage de coton indiqué sur l'étiquette ; renvoie \"\" si l'information n'est pas lisible\",
                    \"polyester_pct\": \"pourcentage de polyester indiqué ; renvoie \"\" si absent ou illisible\",
                    \"polyamide_pct\": \"pourcentage de polyamide indiqué ; renvoie \"\" si absent ou illisible\",
                    \"viscose_pct\": \"pourcentage de viscose indiqué ; renvoie \"\" si absent ou illisible\",
                    \"elastane_pct\": \"pourcentage d'élasthanne indiqué ; renvoie \"\" si absent ou illisible\",
                    \"nylon_pct\": \"pourcentage de nylon indiqué ; renvoie \"\" si absent ou illisible\",
                    \"acrylic_pct\": \"pourcentage d'acrylique indiqué ; renvoie \"\" si absent ou illisible\",
                    \"gender\": \"genre ciblé (femme, homme, mixte) uniquement s'il est explicitement mentionné ; sinon renvoie \"\"\",
                    \"color_main\": \"couleur principale visible ; renvoie \"\" si la couleur n'est pas évidente\",
                    \"defects\": \"défauts ou taches identifiés ; renvoie \"\" s'il n'y en a pas ou qu'ils ne sont pas visibles\",
                    \"defect_tags\": \"liste de slugs parmi [{slugs}] à renseigner UNIQUEMENT si le défaut est visible sur les photos\",
                    \"size_label_visible\": \"true/false : true uniquement si une étiquette de taille est réellement lisible\",
                    \"fabric_label_visible\": \"true/false : true uniquement si une étiquette de composition est réellement lisible\",
                    \"sku\": \"SKU Levi's : JLF + numéro (1-3 chiffres) pour un jean femme, JLH + numéro (1-3 chiffres) pour un jean homme ; renvoie \"\" si l'étiquette n'est pas lisible (ne jamais inventer, le rendu affichera 'SKU/nc')\"
                  }}
                }}
                N'inclus aucun autre texte hors de ce JSON. Les valeurs doivent être au format chaîne, sauf les booléens qui doivent être true/false.
                Indique la coupe en anglais dans 'fit_leg' (ex: bootcut, straight, slim).
                Ne remplis jamais un champ avec une valeur estimée ou supposée ; retourne la chaîne vide quand une information est manquante ou incertaine.
                N'invente jamais de matière : si une fibre n'est pas clairement indiquée ou que la ligne est illisible, renvoie la chaîne vide pour ce champ.
                Renseigne size_label_visible et fabric_label_visible à false par défaut et ne les mets à true que si l'étiquette correspondante est parfaitement lisible.
                Lorsque l'étiquette de taille est absente ou illisible mais qu'une mesure nette du tour de taille est visible, renseigne 'waist_measurement_cm' en centimètres et laisse les champs 'fr_size', 'us_w' et 'us_l' vides.
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

