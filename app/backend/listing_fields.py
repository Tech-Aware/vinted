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
    is_dress: bool = False
    wool_pct: FieldValue = None
    cashmere_pct: FieldValue = None
    nylon_pct: FieldValue = None
    acrylic_pct: FieldValue = None
    knit_pattern: FieldValue = None
    made_in: FieldValue = None
    brand: FieldValue = None
    zip_style: FieldValue = None
    feature_notes: FieldValue = None
    technical_features: FieldValue = None
    has_hood: bool = False
    neckline_style: FieldValue = None
    special_logo: FieldValue = None
    bust_flat_measurement_cm: Optional[float] = None
    length_measurement_cm: Optional[float] = None
    sleeve_measurement_cm: Optional[float] = None
    shoulder_measurement_cm: Optional[float] = None
    waist_flat_measurement_cm: Optional[float] = None
    hem_flat_measurement_cm: Optional[float] = None
    non_size_labels_visible: bool = False

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, template_name: Optional[str] = None
    ) -> "ListingFields":
        template_normalized = (template_name or "").strip().lower()

        optional_fr_size_templates = {
            "template-polaire-outdoor",
            "template-pull-tommy-femme",
        }

        jeans_required_fields = (
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

        template_required_fields = {
            "template-jean-levis-femme": jeans_required_fields,
            "template-pull-tommy-femme": (),
            "template-polaire-outdoor": (
                "color_main",
                "gender",
                "defects",
            ),
        }

        required_fields = template_required_fields.get(
            template_normalized, jeans_required_fields
        )

        missing = [key for key in required_fields if key not in data]
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
        brand = normalize(data.get("brand"))
        zip_style = normalize(data.get("zip_style"))
        feature_notes = normalize(data.get("feature_notes"))
        technical_features = normalize(data.get("technical_features"))
        neckline_style = normalize(data.get("neckline_style"))
        special_logo = normalize(data.get("special_logo"))
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
        non_size_labels_visible = ListingFields._normalize_visibility_flag(
            data.get("non_size_labels_visible"), default=False
        )
        sku = sku_raw.upper() if sku_raw else sku_raw
        manual_sku_provided = ListingFields._normalize_visibility_flag(
            data.get("manual_sku_provided"), default=False
        )
        if template_normalized == "template-polaire-outdoor":
            labels_support_sku = fabric_label_visible and non_size_labels_visible
            if sku and (labels_support_sku or manual_sku_provided):
                sku = ListingFields._normalize_polaire_sku(sku, brand)
            else:
                sku = ""
        elif template_normalized == "template-pull-tommy-femme":
            color_main = color_main or "non précisé"
            gender = gender or "non précisé"
            defects = defects or "non précisé"
        is_cardigan = ListingFields._normalize_visibility_flag(
            data.get("is_cardigan"), default=False
        )
        is_dress = ListingFields._normalize_visibility_flag(
            data.get("is_dress"), default=False
        )
        has_hood = ListingFields._normalize_visibility_flag(
            data.get("has_hood"), default=False
        )

        bust_flat_measurement_cm = ListingFields._parse_measurement(
            data.get("bust_flat_measurement_cm"), field_name="bust_flat_measurement_cm"
        )
        length_measurement_cm = ListingFields._parse_measurement(
            data.get("length_measurement_cm"), field_name="length_measurement_cm"
        )
        sleeve_measurement_cm = ListingFields._parse_measurement(
            data.get("sleeve_measurement_cm"), field_name="sleeve_measurement_cm"
        )
        shoulder_measurement_cm = ListingFields._parse_measurement(
            data.get("shoulder_measurement_cm"), field_name="shoulder_measurement_cm"
        )
        waist_flat_measurement_cm = ListingFields._parse_measurement(
            data.get("waist_flat_measurement_cm"), field_name="waist_flat_measurement_cm"
        )
        hem_flat_measurement_cm = ListingFields._parse_measurement(
            data.get("hem_flat_measurement_cm"), field_name="hem_flat_measurement_cm"
        )

        if sku:
            allowed_patterns: list[str] = []

            if template_normalized == "template-pull-tommy-femme":
                allowed_patterns.append(r"^PTF\d{1,3}$")
            elif template_normalized == "template-polaire-outdoor":
                allowed_patterns.extend([r"^PTNF\d{1,3}$", r"^PC\d{1,3}$"])
            else:
                allowed_patterns.append(r"^JLF\d{1,3}$")

            if not any(re.fullmatch(pattern, sku) for pattern in allowed_patterns):
                if template_normalized == "template-pull-tommy-femme":
                    raise ValueError(
                        "SKU invalide: utilise le préfixe PTF suivi de 1 à 3 chiffres pour le template Pull Tommy femme."
                    )
                if template_normalized == "template-polaire-outdoor":
                    raise ValueError(
                        "SKU invalide: utilise PTNF n pour The North Face ou PC n pour Columbia (1 à 3 chiffres, sans tiret)."
                    )
                raise ValueError(
                    "SKU invalide: utilise le préfixe Levi's autorisé (JLF) suivi de 1 à 3 chiffres."
                )

            if template_normalized == "template-polaire-outdoor" and brand:
                normalized_brand = _normalize_text(brand)
                if "north face" in normalized_brand and not sku.startswith("PTNF"):
                    raise ValueError(
                        "SKU invalide: les articles The North Face doivent utiliser le préfixe PTNF."
                    )
                if "columbia" in normalized_brand and not sku.startswith("PC"):
                    raise ValueError(
                        "SKU invalide: les articles Columbia doivent utiliser le préfixe PC."
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
            brand=brand,
            zip_style=zip_style,
            feature_notes=feature_notes,
            technical_features=technical_features,
            neckline_style=neckline_style,
            special_logo=special_logo,
            has_hood=has_hood,
            is_cardigan=is_cardigan,
            is_dress=is_dress,
            bust_flat_measurement_cm=bust_flat_measurement_cm,
            length_measurement_cm=length_measurement_cm,
            sleeve_measurement_cm=sleeve_measurement_cm,
            shoulder_measurement_cm=shoulder_measurement_cm,
            waist_flat_measurement_cm=waist_flat_measurement_cm,
            hem_flat_measurement_cm=hem_flat_measurement_cm,
            non_size_labels_visible=non_size_labels_visible,
        )

    @staticmethod
    def _normalize_polaire_sku(value: str, brand: FieldValue) -> str:
        """Normalize loosely formatted polaire SKUs before validation."""

        cleaned = value.strip().upper()
        if not cleaned:
            return cleaned

        if (
            cleaned.startswith("PC")
            and len(cleaned) > 3
            and not any(sep in cleaned for sep in (" ", "-"))
        ):
            return ""

        match = re.search(r"(PTNF|PC)[\s-]?(\d+)", cleaned)
        if not match:
            return ""

        prefix = match.group(1)
        digits = match.group(2)
        if len(digits) > 3:
            digits = digits[:3]

        if prefix and digits:
            return f"{prefix}{digits}"

        return ""

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

        measurement_rounded = round(measurement)
        if measurement_rounded < 18:
            return ""
        if measurement_rounded <= 22:
            return "basse"
        if measurement_rounded <= 27:
            return "moyenne"
        if measurement_rounded <= 33:
            return "haute"
        if measurement_rounded >= 34:
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
                    \"fr_size\": \"taille affichée (XS, S, M, etc.) ; renvoie \"\" si non lisible\",
                    \"us_w\": \"laisse ce champ vide pour les pulls (renvoie \"\")\",
                    \"us_l\": \"laisse ce champ vide pour les pulls (renvoie \"\")\",
                    \"fit_leg\": \"laisse ce champ vide pour les pulls (renvoie \"\")\",
                    \"rise_class\": \"laisse ce champ vide pour les pulls (renvoie \"\")\",
                    \"rise_measurement_cm\": \"laisse ce champ vide pour les pulls (renvoie \"\")\",
                    \"waist_measurement_cm\": \"laisse ce champ vide sauf si une mesure précise apparaît clairement\",
                    \"bust_flat_measurement_cm\": \"largeur de poitrine à plat en cm ; multiplie par 2 pour connaître le tour complet (garde la valeur vide si absente)\",
                    \"length_measurement_cm\": \"longueur épaule-ourlet en cm si une mesure nette est visible ; sinon renvoie \"\"\",
                    \"sleeve_measurement_cm\": \"longueur de manche mesurée en cm quand la prise de vue est nette ; sinon renvoie \"\"\",
                    \"shoulder_measurement_cm\": \"largeur d'épaule à plat en cm ; renvoie \"\" si incertaine\",
                    \"waist_flat_measurement_cm\": \"largeur taille à plat en cm ; renvoie \"\" si non mesurée\",
                    \"hem_flat_measurement_cm\": \"largeur bas de vêtement à plat en cm ; renvoie \"\" si non mesurée\",
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
                    \"non_size_labels_visible\": \"true/false : true si une autre étiquette (composition, marque, SKU, consignes d'entretien) est clairement visible sur les photos ; false sinon\",
                    \"sku\": \"SKU Pull Tommy Femme : PTF + numéro (1-3 chiffres) lorsque l'étiquette est lisible ; renvoie \"\" sinon (ne jamais inventer, sinon la génération échouera et le rendu affichera 'SKU/nc')\",
                    \"is_cardigan\": \"true/false : true si l'article est un gilet (avec ouverture complète) ; false sinon\",
                    \"is_dress\": \"true/false : true uniquement si l'article est une robe (pas un pull/gilet) ; false sinon\"
                  }}
                }}
                N'inclus aucun autre texte hors de ce JSON. Les valeurs doivent être au format chaîne, sauf les booléens qui doivent être true/false.
                Ne fournis pas de champ \"model\" pour les pulls Tommy : cette information n'est pas pertinente ; laisse-le absent ou vide.
                Ne remplis jamais un champ avec une valeur estimée ou supposée ; retourne la chaîne vide quand une information est manquante ou incertaine.
                N'invente jamais de matière : si une fibre n'est pas clairement indiquée ou que la ligne est illisible, renvoie la chaîne vide pour ce champ.
                Renseigne size_label_visible et fabric_label_visible à false par défaut et ne les mets à true que si l'étiquette correspondante est parfaitement lisible.
                Si l'étiquette de taille est absente ou floue, laisse strictement vides 'fr_size', 'us_w' et 'us_l' et privilégie les mesures de taille ('waist_measurement_cm' ou 'waist_flat_measurement_cm') lorsqu'elles sont lisibles.
                Mentionne « Made in Europe » uniquement si l'étiquette confirme un pays européen et n'invente jamais de provenance.
                Dans le titre, supprime les pourcentages de laine ou de cachemire lorsqu'ils sont faibles, mais conserve la valeur numérique exacte dans la description et recopie-la dans les champs 'wool_pct' et 'cashmere_pct' dès que l'étiquette est lisible ; écris simplement « coton » si le pourcentage de coton est inférieur à 60%.
                Si une étiquette SKU claire est visible, tu dois recopier exactement la référence PTF correspondante sinon la génération échouera.
                """
            ).strip()
        elif template_name == "template-polaire-outdoor":
            instruction = dedent(
                f"""
                Réponds EXCLUSIVEMENT avec un JSON valide contenant une clé 'fields' structurée comme suit :
                {{
                  \"fields\": {{
                    \"brand\": \"marque lisible (The North Face, Columbia) ; laisse vide si incertain\",
                    \"model\": \"nom ou référence du produit ; renvoie \"\" si aucune info fiable\",
                    \"fr_size\": \"taille FR visible (XS/S/M/...) ; renvoie \"\" si non lisible\",
                    \"us_w\": \"laisse ce champ vide pour les polaires\",
                    \"us_l\": \"laisse ce champ vide pour les polaires\",
                    \"fit_leg\": \"laisse ce champ vide pour les polaires\",
                    \"rise_class\": \"laisse ce champ vide pour les polaires\",
                    \"rise_measurement_cm\": \"laisse vide pour les polaires\",
                    \"waist_measurement_cm\": \"laisse vide pour les polaires\",
                    \"bust_flat_measurement_cm\": \"largeur de poitrine à plat en cm ; laisse vide si absente\",
                    \"length_measurement_cm\": \"longueur dos en cm si une mesure nette est visible ; sinon renvoie \"\"\",
                    \"sleeve_measurement_cm\": \"longueur de manche mesurée ; sinon renvoie \"\"\",
                    \"shoulder_measurement_cm\": \"largeur d'épaule à plat ; sinon renvoie \"\"\",
                    \"waist_flat_measurement_cm\": \"largeur taille à plat ; sinon renvoie \"\"\",
                    \"hem_flat_measurement_cm\": \"largeur bas de vêtement à plat ; sinon renvoie \"\"\",
                    \"cotton_pct\": \"pourcentage de coton lisible ; renvoie \"\" si absent\",
                    \"wool_pct\": \"pourcentage de laine lisible ; renvoie \"\" si absent\",
                    \"cashmere_pct\": \"pourcentage de cachemire lisible ; renvoie \"\" si absent\",
                    \"polyester_pct\": \"pourcentage de polyester lisible ; si aucune autre matière n'est mentionnée dans la boîte Commentaire et qu'aucune étiquette n'est exploitable, renseigne 100\",
                    \"polyamide_pct\": \"pourcentage de polyamide lisible ; renvoie \"\" si absent\",
                    \"viscose_pct\": \"pourcentage de viscose lisible ; renvoie \"\" si absent\",
                    \"elastane_pct\": \"pourcentage d'élasthanne lisible ; renvoie \"\" si absent\",
                    \"nylon_pct\": \"pourcentage de nylon lisible ; renvoie \"\" si absent\",
                    \"acrylic_pct\": \"pourcentage d'acrylique lisible ; renvoie \"\" si absent\",
                    \"gender\": \"genre ciblé (femme, homme, mix) ; renvoie \"\" si incertain\",
                    \"color_main\": \"couleur principale visible\",
                    \"zip_style\": \"type d'ouverture (full zip, 1/4 zip, boutons, col zippé, etc.)\",
                    \"neckline_style\": \"type de col visible (col roulé, col montant, col V, col rond, patte boutonnée, etc.) ; renvoie \"\" si incertain\",
                    \"feature_notes\": \"notes de style (poche kangourou, col montant, ourlet ajustable) ; renvoie \"\" si rien à signaler\",
                    \"technical_features\": \"technologies ou matières (Polartec, Omni-Heat, DryVent, etc.) ; renvoie \"\" si rien à signaler\",
                    \"special_logo\": \"logo ou détail distinctif (ruban rose, écusson commémoratif...) ; renvoie \"\" s'il n'y en a pas\",
                    \"has_hood\": \"true/false : true uniquement si une capuche est visible\",
                    \"defects\": \"défauts ou taches identifiés ; renvoie \"\" s'il n'y en a pas\",
                    \"defect_tags\": \"liste de slugs parmi [{slugs}] à renseigner UNIQUEMENT si le défaut est visible\",
                    \"size_label_visible\": \"true/false : true uniquement si l'étiquette de taille est parfaitement lisible\",
                    \"fabric_label_visible\": \"true/false : true uniquement si l'étiquette de composition est parfaitement lisible\",
                    \"fabric_label_cut\": \"true/false : true si l'étiquette matière a été coupée volontairement ; false sinon\",
                    \"non_size_labels_visible\": \"true/false : true si d'autres étiquettes (marque, made in, instructions) sont visibles\",
                    \"sku\": \"SKU polaire : PTNFn (1 à 3 chiffres) pour The North Face, PCn pour Columbia ; renvoie \"\" si non lisible et ne jamais inventer\"
                  }}
                }}
                N'inclus aucun autre texte hors de ce JSON. Les valeurs doivent être au format chaîne, sauf les booléens qui doivent être true/false.
                Règles spécifiques :
                - Renseigne systématiquement les mesures à plat lorsqu'elles sont visibles, sinon renvoie la chaîne vide.
                - Décris précisément zip_style/neckline_style pour refléter full zip / 1/4 zip / boutons et col roulé / col montant / col V / col rond, et repère les logos ou rubans spéciaux via special_logo.
                - Ne mets la matière dans le titre que lorsque la fibre est intéressante (coton, laine, cachemire, soie) et sans pourcentage.
                - Sauf commentaire explicite dans la boîte Commentaire signalant une matière différente, considère les polaires comme 100% polyester lorsque l'étiquette n'est pas lisible : mets \"polyester_pct\" à \"100\" et laisse les autres fibres vides.
                - Les champs brand/model/zip_style/feature_notes/technical_features ne doivent contenir que des informations confirmées par les photos.
                - has_hood = true uniquement si une capuche est clairement visible.
                - Le SKU doit reprendre exactement le format PTNF + chiffres ou PC + chiffres selon la marque détectée, sans tiret ; renvoie \"\" si l'information est absente.
                - Rappelle les mentions d'étiquettes coupées via fabric_label_visible/fabric_label_cut.
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
                    \"waist_flat_measurement_cm\": \"largeur taille à plat en cm (multiplie par 2 pour retrouver le tour complet) ; renvoie \"\" si absente ou floue\",
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
                    \"non_size_labels_visible\": \"true/false : true si une autre étiquette (composition, marque, SKU, consignes d'entretien) est clairement visible sur les photos ; false sinon\",
                    \"sku\": \"SKU Levi's : JLF + numéro (1-3 chiffres) ; renvoie \"\" si l'étiquette n'est pas lisible (ne jamais inventer, le rendu affichera 'SKU/nc')\"
                  }}
                }}
                N'inclus aucun autre texte hors de ce JSON. Les valeurs doivent être au format chaîne, sauf les booléens qui doivent être true/false.
                Indique la coupe en anglais dans 'fit_leg' (ex: bootcut, straight, slim).
                Ne remplis jamais un champ avec une valeur estimée ou supposée ; retourne la chaîne vide quand une information est manquante ou incertaine.
                N'invente jamais de matière : si une fibre n'est pas clairement indiquée ou que la ligne est illisible, renvoie la chaîne vide pour ce champ.
                Lis systématiquement trois étiquettes distinctes :
                  • l'étiquette principale à l'intérieur de la ceinture pour récupérer UNIQUEMENT la marque Levi's, le code modèle, la hauteur de taille et la coupe ;
                  • l'étiquette de composition pour recopier chaque fibre et son pourcentage ;
                  • l'étiquette de taille placée derrière la composition pour noter précisément le couple W/L.
                Ne retiens aucune autre information figurant sur ces étiquettes et ignore le reste du texte.
                Renseigne size_label_visible et fabric_label_visible à false par défaut et ne les mets à true que si l'étiquette correspondante est parfaitement lisible sur les photos.
                Si l'étiquette de taille est absente, floue ou partiellement masquée, laisse strictement vides 'fr_size', 'us_w' et 'us_l' même si une valeur approximative semble visible, et remplis uniquement 'waist_measurement_cm' ou 'waist_flat_measurement_cm' si une mesure nette est disponible.
                Si l'étiquette de composition est absente, coupée pour plus de confort ou illisible, laisse tous les pourcentages vides, mets 'fabric_label_visible' à false et positionne 'fabric_label_cut' à true uniquement lorsqu'une coupe volontaire est manifeste ; sinon laisse 'fabric_label_cut' à false.
                Lorsque l'étiquette de taille est absente ou illisible mais qu'une mesure nette du tour de taille est visible, renseigne 'waist_measurement_cm' en centimètres et laisse les champs 'fr_size', 'us_w' et 'us_l' vides.
                Si les étiquettes de taille ET de composition ont été retirées pour plus de confort, mets 'size_label_visible' et 'fabric_label_visible' à false et 'fabric_label_cut' à true.
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

