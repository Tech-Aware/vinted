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

"""Listing templates and prompts for the Vinted assistant."""

import re
import unicodedata

from dataclasses import dataclass
from textwrap import dedent
from typing import Callable, Dict, List, Optional, Tuple

from app.backend.defect_catalog import get_defect_descriptions
from app.backend.listing_fields import ListingFields
from app.backend.sizing import (
    NormalizedSizes,
    fr_size_from_waist_measurement,
    normalize_sizes,
)
from app.backend.text_normalization import normalize_fit_terms, translate_color_to_french


def _ensure_percent(value: Optional[str]) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if stripped.endswith("%"):
        return stripped
    return f"{stripped}%"


def _clean(value: Optional[str]) -> str:
    return (value or "").strip()


_SIZE_TOKEN_SPLIT = re.compile(r"[^A-Z0-9]+")


def _normalize_size_hashtag(value: Optional[str], *, default: str = "M") -> str:
    """Return an uppercase token suitable for Durin size hashtags."""

    if not value:
        return default

    normalized = value.strip().upper()
    if not normalized:
        return default

    normalized = normalized.replace("TAILLE", " ")
    tokens = [token for token in _SIZE_TOKEN_SPLIT.split(normalized) if token]

    prioritized_patterns = (
        re.compile(r"^(?:\d+)?X{0,4}[SML]$"),
        re.compile(r"^TU$"),
        re.compile(r"^T[0-9]+$"),
        re.compile(r"^\d{2,3}$"),
    )

    for pattern in prioritized_patterns:
        for token in tokens:
            if pattern.match(token):
                return token

    if tokens:
        return tokens[0]

    fallback = "".join(ch for ch in normalized if ch.isalnum())
    return fallback or default


def _normalize_text_for_comparison(value: str) -> str:
    """Normalize text for accent-insensitive substring checks."""

    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


def _contains_normalized_phrase(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    return _normalize_text_for_comparison(needle) in _normalize_text_for_comparison(haystack)


def _join_fibers(parts: List[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} et {parts[1]}"
    return f"{', '.join(parts[:-1])} et {parts[-1]}"


@dataclass
class ListingTemplate:
    name: str
    description: str
    prompt: str
    render_callback: Callable[[ListingFields], Tuple[str, str]]

    def render(self, fields: ListingFields) -> Tuple[str, str]:
        return self.render_callback(fields)


def render_template_jean_levis_femme(fields: ListingFields) -> Tuple[str, str]:
    fit_title, fit_description, fit_hashtag = normalize_fit_terms(fields.fit_leg)
    measurement_fr = fr_size_from_waist_measurement(
        fields.waist_measurement_cm, ensure_even=True
    )

    if fields.size_label_visible:
        normalized_sizes: NormalizedSizes = normalize_sizes(
            fields.us_w,
            fields.fr_size,
            fields.has_elastane,
            ensure_even_fr=True,
            waist_measurement_cm=fields.waist_measurement_cm,
        )
        fr_display = normalized_sizes.fr_size or _clean(fields.fr_size)
        us_display = normalized_sizes.us_size
        size_note = normalized_sizes.note
    else:
        fr_candidate = _clean(fields.fr_size)
        us_candidate = _clean(fields.us_w)
        size_note = None
        if not fr_candidate and not us_candidate and measurement_fr:
            fr_display = measurement_fr
            us_display = None
            measurement_value = fields.waist_measurement_cm
            if measurement_value is not None:
                size_note = (
                    "Taille estimée à partir d'un tour de taille mesuré à environ "
                    f"{int(round(measurement_value))} cm."
                )
            else:
                size_note = (
                    "Taille estimée à partir du tour de taille mesuré visuellement sur les photos."
                )
        else:
            fr_display = fr_candidate
            us_display = None

    model = (fields.model or "").strip()
    gender = _clean(fields.gender)
    has_context = any(
        _clean(value)
        for value in (
            fields.model,
            fields.fr_size,
            fields.us_w,
            fields.us_l,
            fields.color_main,
            fields.cotton_pct,
            fields.fit_leg,
        )
    )
    gender_value = gender or ("femme" if has_context else "")
    color = translate_color_to_french(fields.color_main)
    color = _clean(color)
    rise = _clean(fields.resolved_rise_class)
    cotton = _ensure_percent(fields.cotton_pct) if fields.fabric_label_visible else ""
    polyester_value = (
        _ensure_percent(fields.polyester_pct) if fields.fabric_label_visible else ""
    )
    viscose_value = (
        _ensure_percent(fields.viscose_pct) if fields.fabric_label_visible else ""
    )
    elastane_value = (
        _ensure_percent(fields.elastane_pct) if fields.fabric_label_visible else ""
    )
    wool_value = (
        _ensure_percent(fields.wool_pct) if fields.fabric_label_visible else ""
    )
    cashmere_value = (
        _ensure_percent(fields.cashmere_pct) if fields.fabric_label_visible else ""
    )
    nylon_value = (
        _ensure_percent(fields.nylon_pct) if fields.fabric_label_visible else ""
    )

    composition_parts: List[str] = []
    if fields.fabric_label_visible:
        if cotton:
            composition_parts.append(f"{cotton} coton")
        if fields.has_wool:
            composition_parts.append(
                f"{wool_value} laine".strip() if wool_value else "laine"
            )
        if fields.has_cashmere:
            composition_parts.append(
                f"{cashmere_value} cachemire".strip()
                if cashmere_value
                else "cachemire"
            )
        if fields.has_viscose and viscose_value:
            composition_parts.append(f"{viscose_value} viscose")
        if fields.has_polyester and polyester_value:
            composition_parts.append(f"{polyester_value} polyester")
        if fields.has_nylon and nylon_value:
            composition_parts.append(f"{nylon_value} nylon")
        if fields.has_elastane and elastane_value:
            composition_parts.append(f"{elastane_value} élasthanne")
        if composition_parts:
            composition_sentence = f"Composition : {_join_fibers(composition_parts)}."
        else:
            composition_sentence = (
                "Composition indiquée sur l'étiquette (voir photos pour les détails)."
            )
    else:
        composition_sentence = (
            "Composition non visible sur les photos (étiquette absente ou illisible)."
        )

    defect_texts = get_defect_descriptions(fields.defect_tags)
    raw_defects = (fields.defects or "").strip()

    positive_state_aliases = {
        "très bon état",
        "très bon état général",
    }
    positive_state_aliases_casefold = {alias.casefold() for alias in positive_state_aliases}
    if raw_defects.casefold() in positive_state_aliases_casefold:
        raw_defects = ""

    if defect_texts:
        defects = ", ".join(defect_texts)
    else:
        defects = raw_defects if raw_defects else ""
    sku = (fields.sku or "").strip()
    fit_title_text = fit_title or _clean(fields.fit_leg)
    fit_description_text = fit_description or _clean(fields.fit_leg)
    fit_hashtag_source = fit_hashtag or _clean(fields.fit_leg)
    fit_hashtag_text = (
        fit_hashtag_source.lower().replace(" ", "") if fit_hashtag_source else ""
    )

    title_intro = "Jean Levi’s"
    if model:
        title_intro = f"{title_intro} {model}"

    cotton_title_segment = f"{cotton} coton" if cotton else ""
    title_parts: List[str] = [title_intro]
    if fr_display:
        title_parts.append(f"FR{fr_display}")
    if fields.size_label_visible and us_display:
        title_parts.append(f"W{us_display}")
    if fields.size_label_visible and fields.us_l:
        title_parts.append(f"L{fields.us_l}")
    if fit_title_text:
        title_parts.extend(["coupe", fit_title_text])
    if cotton_title_segment:
        title_parts.append(cotton_title_segment)
    if gender_value:
        title_parts.append(gender_value)
    if color:
        title_parts.append(color)
    if sku:
        title_parts.extend(["-", sku])
    title = " ".join(part for part in title_parts if part).replace("  ", " ").strip()

    size_fragments: List[str] = []
    if us_display and fr_display:
        size_fragments.append(f"Taille {us_display} US (équivalent {fr_display} FR)")
    elif us_display:
        size_fragments.append(f"Taille {us_display} US")
    elif fr_display:
        size_fragments.append(f"Taille {fr_display} FR")
    else:
        size_fragments.append("Taille non précisée")
    fit_phrase = fit_description_text or "non précisée"
    rise_phrase = rise or "non précisée"
    size_fragments.append(f"coupe {fit_phrase}")
    size_fragments.append(f"à taille {rise_phrase}")
    size_sentence = ", ".join(size_fragments) + ", pour une silhouette ajustée et confortable."

    if model and gender_value:
        first_sentence = f"Jean Levi’s modèle {model} pour {gender_value}."
    elif model:
        first_sentence = f"Jean Levi’s modèle {model}."
    elif gender_value:
        first_sentence = f"Jean Levi’s pour {gender_value}."
    else:
        first_sentence = "Jean Levi’s."

    first_paragraph_lines = [
        first_sentence,
        size_sentence,
    ]
    if size_note:
        first_paragraph_lines.append(size_note)

    if color:
        color_sentence = (
            f"Coloris {color} légèrement délavé, très polyvalent et facile à assortir."
        )
    else:
        color_sentence = "Coloris non précisé, se référer aux photos pour les nuances."

    second_paragraph_lines = [
        color_sentence,
        composition_sentence,
        "Fermeture zippée + bouton gravé Levi’s.",
    ]

    third_paragraph_lines: List[str] = []
    if defects:
        third_paragraph_lines.append(f"Très bon état : {defects} (voir photos)")
    else:
        third_paragraph_lines.append("Très bon état")

    if not fields.size_label_visible and not fields.fabric_label_visible:
        third_paragraph_lines.append(
            "Étiquettes taille et composition non visibles sur les photos."
        )
    elif not fields.size_label_visible:
        third_paragraph_lines.append("Étiquette taille non visible sur les photos.")
    elif not fields.fabric_label_visible:
        third_paragraph_lines.append("Étiquette composition non visible sur les photos.")

    third_paragraph_lines.extend(
        [
            "📏 Mesures précises visibles en photo.",
            "📦 Envoi rapide et soigné",
        ]
    )

    fr_tag = (fr_display or "nc").lower()
    fourth_paragraph_lines = [
        f"✨ Retrouvez tous mes articles Levi’s à votre taille ici 👉 #durin31fr{fr_tag}",
        "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !",
    ]

    hashtags_tokens: List[str] = []
    for token in [
        "#levis",
        "#jeanlevis",
        "#jeandenim",
        f"#levis{gender_value.lower().replace(' ', '')}" if gender_value else "",
        f"#{fit_hashtag_text}jean" if fit_hashtag_text else "",
        f"#{rise.lower().replace(' ', '')}" if rise else "",
        f"#jean{color.lower().replace(' ', '')}" if color else "",
        f"#durin31fr{fr_tag}",
    ]:
        token_clean = token.strip()
        if token_clean and token_clean not in hashtags_tokens:
            hashtags_tokens.append(token_clean)
    hashtags_paragraph_lines = [" ".join(hashtags_tokens)]

    description = "\n\n".join(
        [
            "\n".join(first_paragraph_lines),
            "\n".join(second_paragraph_lines),
            "\n".join(third_paragraph_lines),
            "\n".join(fourth_paragraph_lines),
            "\n".join(hashtags_paragraph_lines),
        ]
    ).strip()

    return title, description


def build_tommy_marketing_highlight(
    fields: ListingFields, pattern_lower: str
) -> str:
    """Return a marketing highlight sentence tailored to the knit composition."""

    cotton_value = fields.cotton_percentage_value
    cotton_percent = _ensure_percent(fields.cotton_pct) if fields.cotton_pct else ""
    base_sentence: str

    if fields.has_cashmere and fields.has_wool:
        base_sentence = (
            "Maille premium associant laine cosy et cachemire luxueux pour une douceur"
            " enveloppante"
        )
    elif fields.has_cashmere:
        if cotton_value is not None and cotton_value >= 40:
            base_sentence = (
                f"Maille luxueuse mêlant {cotton_percent} coton respirant et une touche"
                " de cachemire pour une douceur irrésistible"
            )
        else:
            base_sentence = (
                "Maille luxueuse sublimée par du cachemire pour une douceur irrésistible"
            )
    elif fields.has_wool:
        if cotton_value is not None and cotton_value >= 40:
            base_sentence = (
                f"Laine chaude associée à {cotton_percent} coton pour rester cosy sans"
                " étouffer"
            )
        elif "torsad" in pattern_lower:
            base_sentence = "Maille torsadée en laine qui enveloppe chaleureusement"
        else:
            base_sentence = "Laine douce et chaude idéale pour affronter les journées fraîches"
    elif cotton_value:
        if cotton_value >= 80:
            base_sentence = (
                f"{cotton_percent} coton respirant pour un confort naturel toute la journée"
            )
        elif cotton_value >= 50:
            base_sentence = (
                f"Maille composée de {cotton_percent} coton pour une sensation douce et respirante"
            )
        else:
            base_sentence = (
                "Présence de coton pour apporter douceur et respirabilité au quotidien"
            )
    else:
        base_sentence = "Maille Tommy Hilfiger confortable au quotidien"

    pattern_phrase = ""
    if pattern_lower:
        if "torsad" in pattern_lower:
            pattern_phrase = " Les torsades apportent du relief cosy."
            if "cosy" in base_sentence.lower():
                pattern_phrase = " Les torsades apportent du relief texturé."
        elif "marini" in pattern_lower:
            pattern_phrase = " L'esprit marinière signe une allure marine iconique."
        elif "ray" in pattern_lower:
            pattern_phrase = " Les rayures dynamisent la silhouette."
        else:
            pattern_phrase = f" Motif {pattern_lower} pour une touche originale."

    base_sentence = base_sentence.rstrip(". ")
    if base_sentence:
        base_sentence = f"{base_sentence}."
    highlight = f"{base_sentence}{pattern_phrase}" if base_sentence else pattern_phrase
    return highlight.strip()


def render_template_pull_tommy_femme(fields: ListingFields) -> Tuple[str, str]:
    size_value = _clean(fields.fr_size)
    size_for_title = size_value.upper() if size_value else ""
    gender_value = _clean(fields.gender) or "femme"
    color = translate_color_to_french(fields.color_main)
    color = _clean(color)
    pattern = _clean(fields.knit_pattern)
    sku = (fields.sku or "").strip()

    cotton_percent = _ensure_percent(fields.cotton_pct) if fields.cotton_pct else ""
    cotton_value = fields.cotton_percentage_value

    material_segment = ""
    pattern_lower = pattern.lower() if pattern else ""
    if fields.has_cashmere:
        material_segment = "en cachemire"
    elif fields.has_wool:
        material_segment = (
            "en laine torsadée" if "torsad" in pattern_lower else "en laine"
        )
    elif cotton_percent:
        if cotton_value is not None and cotton_value >= 60:
            material_segment = f"{cotton_percent} coton"
        else:
            material_segment = "coton"
    elif fields.fabric_label_visible and fields.cotton_pct:
        material_segment = "coton"

    color_tokens: List[str] = []
    if color:
        color_tokens.append(color)
    if pattern and not _contains_normalized_phrase(material_segment, pattern):
        if not _contains_normalized_phrase(color, pattern):
            color_tokens.append(pattern)
    color_phrase = " ".join(token for token in color_tokens if token)

    title_parts = ["Pull Tommy femme"]
    if size_for_title:
        title_parts.append(f"taille {size_for_title}")
    elif size_value:
        title_parts.append(f"taille {size_value}")
    if material_segment:
        title_parts.append(material_segment)
    if color_phrase:
        title_parts.append(color_phrase)
    if fields.made_in_europe:
        title_parts.append("Made in Europe")
    if sku:
        title_parts.extend(["-", sku])
    title = " ".join(part for part in title_parts if part).replace("  ", " ").strip()

    size_sentence = size_for_title or size_value or "non précisée"
    first_sentence = (
        f"Pull Tommy Hilfiger pour {gender_value} taille {size_sentence}."
    )

    if color_phrase:
        style_sentence = (
            f"Coloris {color_phrase} facile à associer pour un look intemporel."
        )
    else:
        style_sentence = "Coloris non précisé, se référer aux photos pour les nuances."

    def build_composition_sentence() -> str:
        if not fields.fabric_label_visible:
            return (
                "Composition non visible sur les photos (étiquette absente ou illisible)."
            )

        def _normalized_percent(value: Optional[str]) -> Tuple[str, Optional[float]]:
            if not value:
                return "", None
            stripped = value.strip()
            if not stripped:
                return "", None
            percent_text = _ensure_percent(stripped)
            numeric_value: Optional[float]
            try:
                numeric_source = (
                    stripped.replace("%", "").replace(",", ".").replace(" ", "")
                )
                numeric_value = float(numeric_source)
            except ValueError:
                numeric_value = None
            return percent_text, numeric_value

        def _append_material(
            percent_value: Optional[str], presence_hint: bool, label: str
        ) -> None:
            percent_text, numeric_value = _normalized_percent(percent_value)
            if numeric_value is not None:
                if numeric_value > 0:
                    parts.append(f"{percent_text} {label}")
                return
            if percent_text:
                parts.append(f"{percent_text} {label}")
            elif presence_hint:
                parts.append(label)

        parts: List[str] = []
        cotton_present = bool((fields.cotton_pct or "").strip())
        _append_material(fields.cotton_pct, cotton_present, "coton")
        _append_material(fields.wool_pct, fields.has_wool, "laine")
        _append_material(fields.cashmere_pct, fields.has_cashmere, "cachemire")
        _append_material(fields.viscose_pct, fields.has_viscose, "viscose")
        _append_material(fields.acrylic_pct, fields.has_acrylic, "acrylique")
        _append_material(fields.polyester_pct, fields.has_polyester, "polyester")
        _append_material(fields.nylon_pct, fields.has_nylon, "nylon")
        _append_material(fields.elastane_pct, fields.has_elastane, "élasthanne")

        if parts:
            return f"Composition : {_join_fibers(parts)}."
        return "Composition indiquée sur l'étiquette (voir photos pour les détails)."

    composition_sentence = build_composition_sentence()

    made_in_sentence = ""
    made_in_detail = _clean(fields.made_in)
    if fields.made_in_europe:
        if made_in_detail:
            made_in_sentence = f"Fabriqué en Europe ({made_in_detail})."
        else:
            made_in_sentence = "Fabriqué en Europe."

    defect_texts = get_defect_descriptions(fields.defect_tags)
    raw_defects = (fields.defects or "").strip()
    positive_state_aliases = {
        "très bon état",
        "très bon état général",
    }
    positive_state_aliases_casefold = {alias.casefold() for alias in positive_state_aliases}
    if raw_defects.casefold() in positive_state_aliases_casefold:
        raw_defects = ""
    if defect_texts:
        defects = ", ".join(defect_texts)
    else:
        defects = raw_defects if raw_defects else ""

    first_paragraph_lines = [first_sentence, style_sentence]

    marketing_highlight = build_tommy_marketing_highlight(fields, pattern_lower)

    second_paragraph_lines = [marketing_highlight, composition_sentence]
    if made_in_sentence:
        second_paragraph_lines.append(made_in_sentence)

    third_paragraph_lines: List[str] = []
    if defects:
        third_paragraph_lines.append(f"Très bon état : {defects} (voir photos)")
    else:
        third_paragraph_lines.append("Très bon état")

    if not fields.size_label_visible and not fields.fabric_label_visible:
        third_paragraph_lines.append(
            "Étiquettes taille et composition non visibles sur les photos."
        )
    elif not fields.size_label_visible:
        third_paragraph_lines.append("Étiquette taille non visible sur les photos.")
    elif not fields.fabric_label_visible:
        third_paragraph_lines.append("Étiquette composition non visible sur les photos.")

    third_paragraph_lines.extend(
        [
            "📏 Mesures détaillées visibles en photo pour plus de précisions.",
            "📦 Envoi rapide et soigné",
        ]
    )

    size_hashtag = _normalize_size_hashtag(size_for_title or size_value)

    fourth_paragraph_lines = [
        f"✨ Retrouvez tous mes pulls Tommy femme ici 👉 #durin31tf{size_hashtag}",
        "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !",
    ]

    hashtags: List[str] = []

    def add_hashtag(tag: str) -> None:
        tag_clean = tag.strip()
        if tag_clean and tag_clean not in hashtags:
            hashtags.append(tag_clean)

    add_hashtag("#tommyhilfiger")
    add_hashtag("#pulltommy")
    add_hashtag("#tommy")
    add_hashtag("#pullfemme")
    add_hashtag("#modefemme")
    add_hashtag("#preloved")
    add_hashtag(f"#durin31tf{size_hashtag}")
    add_hashtag("#ptf")

    if cotton_value is not None and cotton_value > 0:
        add_hashtag("#pullcoton")
    if fields.has_wool:
        add_hashtag("#pulllaine")
    if fields.has_cashmere:
        add_hashtag("#pullcachemire")
    if pattern_lower:
        if "marini" in pattern_lower:
            add_hashtag("#mariniere")
        if "torsad" in pattern_lower:
            add_hashtag("#pulltorsade")
    if color:
        primary_color = color.split()[0].lower()
        add_hashtag(f"#pull{primary_color}")

    fallback_tags = ["#vetementsfemme", "#modepreloved", "#lookintemporel"]
    for tag in fallback_tags:
        if len(hashtags) >= 10:
            break
        add_hashtag(tag)

    hashtags_tokens = hashtags[:10]
    hashtags_paragraph_lines = [" ".join(hashtags_tokens)]

    description = "\n\n".join(
        [
            "\n".join(first_paragraph_lines),
            "\n".join(second_paragraph_lines),
            "\n".join(third_paragraph_lines),
            "\n".join(fourth_paragraph_lines),
            "\n".join(hashtags_paragraph_lines),
        ]
    ).strip()

    return title, description


class ListingTemplateRegistry:
    """Registry holding available listing templates."""

    def __init__(self) -> None:
        self._templates: Dict[str, ListingTemplate] = {
            "template-jean-levis-femme": ListingTemplate(
                name="template-jean-levis-femme",
                description="Template Levi's femme",
                prompt=dedent(
                    """
                    Prend en considération cette légende :
                    - Taille FR = taille française en cm, au format FR{{fr_size}}
                    - Modèle = code numérique du jean (ex: 501). Ajoute uniquement le mot "Premium" si et seulement si indiqué sur l'étiquette.
                    - Wn Ln = valeurs d’étiquette, {{w}} et {{l}}
                    - Coupe = {{fit_leg}} (insère la hauteur de taille {{rise_class}} dans la description uniquement, jamais dans le titre)
                    - Matière = {{cotton_pct}}% coton (+ {{polyester_pct}}% polyester si présent, + {{elastane_pct}}% élasthanne si présent)
                    - Genre = {{gender}}  (valeurs attendues : femme, homme, mix)
                    - Tâches et défauts = Ce qui doit impérativement apparaître dans l'annonce si identifié sur photos ou fournit en commentaire {{defects}}
                    - SKU = {{sku}} (utilise JLF + numéro (1 à 3 chiffres) si jean femme, JLH + numéro si jean homme ;
                      reprends exactement le numéro présent sur l’étiquette blanche visible sur le jean)

                    Utilise ce format :
                    TITRE
                    Jean Levi’s {{model}} FR{{fr_size}} W{{w}} L{{l}} coupe {{fit_leg}} {{cotton_pct}}% coton {{gender}} {{color_main}} - {{sku}}
                    
                    DESCRIPTION + HASHTAG
                    Jean Levi’s modèle {{model}} pour {{gender}}.
                    Taille {{w}} US (équivalent {{fr_size}} FR), coupe {{fit_leg}} à taille {{rise_class}}, pour une silhouette ajustée et confortable.
                    Coloris {{color_main}} légèrement délavé, très polyvalent et facile à assortir.
                    Composition : {{cotton_pct}}% coton{{#if polyester_pct}}, {{polyester_pct}}% polyester{{/if}}{{#if elastane_pct}}, {{elastane_pct}}% élasthanne{{/if}} pour une touche de stretch et plus de confort.
                    Fermeture zippée + bouton gravé Levi’s.
                    
                    Très bon état général {{defects}} (voir photos). S'il n'y a aucun défaut à signaler, écris simplement « Très bon état ».
                    📏 Mesures précises visibles en photo.
                    📦 Envoi rapide et soigné
                    
                    ✨ Retrouvez tous mes articles Levi’s à votre taille ici 👉 #durin31fr{{fr_size}}
                    💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !
                    
                    #levis #jeanlevis #levis{{gender}} #{{fit_leg}}jean #jeandenim #{{rise_class}} #jean{{color_main}} #vintedfr #durin31fr{{fr_size}}

                    Remplis les champs entre accolades en analysant les photos et en utilisant les commentaires.
                    """
                ).strip(),
                render_callback=render_template_jean_levis_femme,
            ),
            "template-pull-tommy-femme": ListingTemplate(
                name="template-pull-tommy-femme",
                description="Template Pull Tommy femme",
                prompt=dedent(
                    """
                    Prend en considération cette légende :
                    - Taille = {{fr_size}} (taille visible sur l'étiquette, format XS/S/M/L/XL)
                    - Couleur = {{color_main}} (décris les couleurs principales visibles)
                    - Motif / maille = {{knit_pattern}} (marinière, torsadé, col V, etc.)
                    - Composition = {{cotton_pct}}, {{wool_pct}}, {{cashmere_pct}}, {{polyester_pct}}, {{viscose_pct}}, {{elastane_pct}} telles qu'indiquées sur l'étiquette
                    - Made in = {{made_in}} (copie exactement la mention écrite)
                    - Défauts = {{defects}} (détaille chaque imperfection visible)
                    - SKU = {{sku}} (utilise PTF + numéro (1 à 3 chiffres) lorsque l'étiquette blanche est lisible)
                    - {{matiere_principale}} = synthèse des matières dominantes (ex : 100% coton, laine torsadée, cachemire)
                    - {{made_in_europe}} = écris « Made in Europe » uniquement si l'étiquette indique un pays européen, sinon laisse vide

                    Règles :
                    - Pour le coton, si le pourcentage est inférieur à 60 %, écris simplement « coton ».
                    - Dans le titre, supprime les pourcentages de laine ou de cachemire lorsqu'ils sont faibles, mais dans la description et les champs ({{wool_pct}}/{{cashmere_pct}}) recopie la valeur numérique exacte indiquée dès que l'étiquette est lisible.
                    - Signale systématiquement lorsque les étiquettes taille/composition sont absentes ou illisibles.
                    - Mentionne « Made in Europe » uniquement si l'étiquette affiche un pays européen confirmé (France, Portugal, Italie, Espagne, etc.).
                    - Rappelle que les mesures sont visibles sur les photos pour plus de précision.

                    Utilise ce format :
                    TITRE
                    Pull Tommy femme taille {{fr_size}} {{matiere_principale}} {{color_main}} {{knit_pattern}} {{made_in_europe}} - {{sku}}

                    DESCRIPTION + HASHTAG
                    Pull Tommy Hilfiger pour femme taille {{fr_size}}.
                    Coloris {{color_main}} {{knit_pattern}}, parfait pour un look intemporel.
                    Composition : {{cotton_pct}}% coton{{#if wool_pct}}, laine{{/if}}{{#if cashmere_pct}}, cachemire{{/if}}{{#if polyester_pct}}, {{polyester_pct}}% polyester{{/if}}{{#if viscose_pct}}, {{viscose_pct}}% viscose{{/if}}{{#if elastane_pct}}, {{elastane_pct}}% élasthanne{{/if}} (adapte selon l'étiquette visible).
                    {{#if made_in}}Fabriqué en Europe {{made_in}} (uniquement si l'étiquette le confirme).{{/if}}
                    Très bon état {{defects}} (voir photos).
                    📏 Mesures détaillées visibles en photo.
                    📦 Envoi rapide et soigné

                    ✨ Retrouvez tous mes pulls Tommy femme ici 👉 #durin31tfM
                    💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !

                    #tommyhilfiger #pulltommy #pullfemme #modefemme #preloved #durin31tfM

                    Remplis les champs entre accolades en analysant les photos et en utilisant les commentaires.
                    """
                ).strip(),
                render_callback=render_template_pull_tommy_femme,
            ),
        }
        self.default_template = "template-jean-levis-femme"

    @property
    def available_templates(self) -> List[str]:
        return list(self._templates)

    def get_prompt(self, name: str) -> str:
        if name not in self._templates:
            raise KeyError(f"Template inconnu: {name}")
        return self._templates[name].prompt

    def get_template(self, name: str) -> ListingTemplate:
        if name not in self._templates:
            raise KeyError(f"Template inconnu: {name}")
        return self._templates[name]
