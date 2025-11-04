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
    estimate_fr_top_size,
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


def _normalize_apparel_fr_size(value: Optional[str]) -> str:
    """Normalize apparel size labels to a consistent FR-friendly format."""

    cleaned = _clean(value)
    if not cleaned:
        return ""

    collapsed = re.sub(r"\s+", "", cleaned).upper()
    match = re.fullmatch(r"(\d+)X", collapsed)
    if not match:
        return cleaned

    count = int(match.group(1))
    if count <= 0:
        return collapsed
    if count <= 3:
        return "X" * count + "L"
    return f"{count}XL"


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


def _extract_primary_size_label(value: Optional[str]) -> Optional[str]:
    """Return the core size value (e.g. ``XL`` from ``FR 42 (XL)``)."""

    if not value:
        return None

    match = re.search(r"\(([^)]+)\)", value)
    if match:
        return match.group(1).strip() or value.strip()

    return value.strip()


def _format_measurement(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    if value <= 0:
        return None
    return f"~{int(round(value))} cm"


def _is_waist_measurement_note(note: Optional[str]) -> bool:
    if not note:
        return False
    normalized = note.strip().casefold()
    return normalized.startswith("taille estimée à partir du tour de taille") or normalized.startswith(
        "taille estimée à partir d'un tour de taille"
    )


def _normalize_text_for_comparison(value: str) -> str:
    """Normalize text for accent-insensitive substring checks."""

    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


def _contains_normalized_phrase(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    return _normalize_text_for_comparison(needle) in _normalize_text_for_comparison(haystack)


_NECKLINE_CANDIDATES = (
    "col v",
    "col en v",
    "encolure v",
    "encolure en v",
    "col rond",
    "encolure ronde",
    "col bateau",
    "encolure bateau",
    "col montant",
    "col roulé",
    "col roulee",
    "encolure roulée",
    "encolure roulee",
    "col cheminée",
    "col cheminee",
    "col tunisien",
    "col zippé",
    "col zippe",
    "col henley",
    "col polo",
    "col camionneur",
)


def split_neckline_from_pattern(pattern: Optional[str]) -> Tuple[str, str]:
    """Return remaining pattern text and detected neckline substring."""

    text = (pattern or "").strip()
    if not text:
        return "", ""

    normalized_chars: List[str] = []
    index_map: List[int] = []
    for index, char in enumerate(text):
        decomposed = unicodedata.normalize("NFKD", char)
        for piece in decomposed:
            if unicodedata.combining(piece):
                continue
            normalized_chars.append(piece.casefold())
            index_map.append(index)

    normalized_text = "".join(normalized_chars)
    if not normalized_text:
        return text, ""

    for candidate in _NECKLINE_CANDIDATES:
        candidate_norm = _normalize_text_for_comparison(candidate)
        if not candidate_norm:
            continue
        pattern_re = re.compile(rf"(?<!\w){re.escape(candidate_norm)}(?!\w)")
        match = pattern_re.search(normalized_text)
        if not match:
            continue

        start_norm = match.start()
        end_norm = match.end() - 1
        start_index = index_map[start_norm]
        end_index = index_map[end_norm] + 1
        neckline_original = text[start_index:end_index].strip()

        before = text[:start_index].rstrip()
        after = text[end_index:].lstrip()
        residual_parts = [segment for segment in (before, after) if segment]
        residual_pattern = " ".join(residual_parts)
        return residual_pattern, neckline_original

    return text, ""


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

    size_note: Optional[str] = None
    size_estimated = False

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
        if _is_waist_measurement_note(size_note):
            size_estimated = True
            size_note = None
    else:
        fr_candidate = _clean(fields.fr_size)
        us_candidate = _clean(fields.us_w)
        if not fr_candidate and not us_candidate and measurement_fr:
            fr_display = measurement_fr
            us_display = None
            size_estimated = True
        else:
            fr_display = fr_candidate
            us_display = None

    size_label_missing = not fields.size_label_visible
    composition_label_unavailable = (not fields.fabric_label_visible) or fields.fabric_label_cut

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
    polyamide_value = (
        _ensure_percent(fields.polyamide_pct) if fields.fabric_label_visible else ""
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

    size_label_cut_message = "Étiquette taille coupée pour plus de confort."
    composition_label_cut_message = "Étiquette composition coupée pour plus de confort."
    combined_label_cut_message = "Étiquette taille et compos coupées pour plus de confort."

    composition_parts: List[str] = []
    if composition_label_unavailable:
        if size_label_missing:
            composition_sentence = combined_label_cut_message
        else:
            composition_sentence = composition_label_cut_message
    elif fields.fabric_label_visible:
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
        if fields.has_polyamide and polyamide_value:
            composition_parts.append(f"{polyamide_value} polyamide")
        if fields.has_nylon and nylon_value:
            composition_parts.append(f"{nylon_value} nylon")
        if fields.has_elastane and elastane_value:
            composition_parts.append(f"{elastane_value} élasthanne")
        if composition_parts:
            composition_sentence = f"Composition : {_join_fibers(composition_parts)}."
        else:
            composition_sentence = (
                "Composition non lisible sur l'étiquette (voir photos pour confirmation)."
            )
    else:
        composition_sentence = "Composition non lisible sur l'étiquette (voir photos pour confirmation)."

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
    sku_display = sku if sku else "SKU/nc"
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
    title_parts.extend(["-", sku_display])
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
    size_sentence_core = ", ".join(size_fragments)
    if size_estimated:
        size_sentence_core = f"{size_sentence_core} (voir photos)"
    size_sentence = (
        f"{size_sentence_core}, pour une silhouette ajustée et confortable."
    )

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

    label_notice: Optional[str] = None
    if size_label_missing and not composition_label_unavailable:
        label_notice = size_label_cut_message
    elif size_label_missing and composition_label_unavailable:
        if composition_sentence.strip() != combined_label_cut_message:
            label_notice = combined_label_cut_message
    elif composition_label_unavailable:
        if composition_sentence.strip() not in (
            composition_label_cut_message,
            combined_label_cut_message,
        ):
            label_notice = composition_label_cut_message

    if label_notice:
        existing_lines = second_paragraph_lines + third_paragraph_lines
        if not any(label_notice == line.strip() for line in existing_lines):
            third_paragraph_lines.append(label_notice)

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


@dataclass(frozen=True)
class PatternRule:
    tokens: Tuple[str, ...]
    marketing: str
    style: str
    hashtags: Tuple[str, ...]
    material_override: Optional[str] = None


PATTERN_RULES: Tuple[PatternRule, ...] = (
    PatternRule(
        tokens=("losang", "argyle", "ecoss"),
        marketing="{base_sentence} Les losanges écossais apportent une touche preppy iconique.",
        style="Motif argyle chic qui dynamise la silhouette.",
        hashtags=("#{item_label_lower}losange", "#argyle"),
    ),
    PatternRule(
        tokens=("ray", "stripe"),
        marketing="{base_sentence} Les rayures dynamisent la silhouette.",
        style="Les rayures insufflent une allure graphique intemporelle.",
        hashtags=("#{item_label_lower}rayure", "#rayures"),
    ),
    PatternRule(
        tokens=("chevron", "herringbone"),
        marketing="{base_sentence} Le motif chevron structure le look avec élégance.",
        style="Motif chevron travaillé pour une allure sophistiquée.",
        hashtags=("#{item_label_lower}chevron",),
    ),
    PatternRule(
        tokens=("damier", "checker", "echiquier"),
        marketing="{base_sentence} Le motif damier apporte une touche graphique affirmée.",
        style="Damier contrasté pour un twist visuel fort.",
        hashtags=("#{item_label_lower}damier",),
    ),
    PatternRule(
        tokens=("jacquard", "fairisle"),
        marketing="{base_sentence} La maille jacquard dévoile un motif travaillé très cosy.",
        style="Jacquard riche en détails pour une allure chaleureuse.",
        hashtags=("#{item_label_lower}jacquard", "#fairisle"),
    ),
    PatternRule(
        tokens=("torsad", "aran", "cable"),
        marketing="{base_sentence} Les torsades apportent du relief cosy.",
        style="Maille torsadée iconique au charme artisanal.",
        hashtags=("#{item_label_lower}torsade",),
        material_override="en laine torsadée",
    ),
    PatternRule(
        tokens=("pointderiz", "niddabeille", "seedstitch", "waffle"),
        marketing="{base_sentence} La texture en relief apporte du volume et de la douceur.",
        style="Maille texturée qui joue sur les reliefs délicats.",
        hashtags=("#{item_label_lower}texturé",),
    ),
    PatternRule(
        tokens=("pieddepoule", "pieddecoq", "houndstooth"),
        marketing="{base_sentence} Le motif pied-de-poule signe une allure rétro-chic.",
        style="Pied-de-poule graphique pour une silhouette élégante.",
        hashtags=("#{item_label_lower}pieddepoule",),
    ),
    PatternRule(
        tokens=("nordique", "scandinave", "flocon", "renne"),
        marketing="{base_sentence} L’esprit nordique réchauffe vos looks d’hiver.",
        style="Motif nordique douillet esprit chalet.",
        hashtags=("#{item_label_lower}nordique",),
    ),
    PatternRule(
        tokens=("boheme", "ethnique", "azt", "tribal"),
        marketing="{base_sentence} Le motif bohème diffuse une vibe folk et décontractée.",
        style="Motif bohème pour une allure folk décontractée.",
        hashtags=("#{item_label_lower}boheme",),
    ),
    PatternRule(
        tokens=("colorblock",),
        marketing="{base_sentence} Le color block joue sur les contrastes audacieux.",
        style="Color block énergique qui capte l’œil.",
        hashtags=("#{item_label_lower}colorblock",),
    ),
    PatternRule(
        tokens=("degrade", "ombre", "gradient", "dipdye"),
        marketing="{base_sentence} Le dégradé nuance la maille avec subtilité.",
        style="Dégradé vaporeux pour un rendu tout en douceur.",
        hashtags=("#{item_label_lower}degrade",),
    ),
    PatternRule(
        tokens=("logo", "brand", "monogram"),
        marketing="{base_sentence} Le logo mis en avant affirme le style Tommy.",
        style="Logo signature mis en valeur pour un look assumé.",
        hashtags=("#{item_label_lower}logo",),
    ),
    PatternRule(
        tokens=("graphique", "abstrait", "abstract", "graphic"),
        marketing="{base_sentence} Le motif graphique apporte une touche arty.",
        style="Graphismes audacieux pour une silhouette arty.",
        hashtags=("#{item_label_lower}graphique",),
    ),
)


def _find_pattern_rule(pattern_normalized: str) -> Optional[PatternRule]:
    if not pattern_normalized:
        return None
    compact = re.sub(r"[^a-z0-9]", "", pattern_normalized)
    for rule in PATTERN_RULES:
        for token in rule.tokens:
            if token in pattern_normalized or (compact and token in compact):
                return rule
    return None


def build_tommy_marketing_highlight(
    fields: ListingFields, pattern_value: Optional[str]
) -> str:
    """Return a marketing highlight sentence tailored to the knit composition."""

    pattern_clean = _clean(pattern_value)
    pattern_remaining, neckline_value = split_neckline_from_pattern(pattern_clean)
    pattern_lower = pattern_remaining.lower()

    cotton_value = fields.cotton_percentage_value
    cotton_percent = _ensure_percent(fields.cotton_pct) if fields.cotton_pct else ""
    base_sentence: str

    if fields.is_pure_cotton:
        base_sentence = "Maille 100% coton pour un toucher doux et léger"
    elif fields.has_cashmere and fields.has_wool:
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

    base_sentence_clean = base_sentence.rstrip(". ")
    base_sentence_text = f"{base_sentence_clean}." if base_sentence_clean else ""

    pattern_normalized = (
        _normalize_text_for_comparison(pattern_lower) if pattern_lower else ""
    )
    rule = _find_pattern_rule(pattern_normalized)

    if rule:
        formatted = rule.marketing.format(base_sentence=base_sentence_text).strip()
        if not neckline_value:
            return formatted or base_sentence_text
        neckline_sentence = (
            f"{neckline_value[0].upper() + neckline_value[1:]} pour une jolie finition."
        )
        return " ".join(segment for segment in (formatted, neckline_sentence) if segment).strip()

    pattern_sentence = ""
    if pattern_lower:
        if "marini" in pattern_normalized:
            pattern_sentence = "L'esprit marinière signe une allure marine iconique."
        else:
            pattern_sentence = f"Motif {pattern_lower} pour une touche originale."

    neckline_sentence = ""
    if neckline_value:
        neckline_sentence = (
            f"{neckline_value[0].upper() + neckline_value[1:]} pour une jolie finition."
        )

    segments = [segment for segment in (base_sentence_text, pattern_sentence, neckline_sentence) if segment]
    highlight = " ".join(segments)
    return highlight.strip()


def render_template_pull_tommy_femme(fields: ListingFields) -> Tuple[str, str]:
    size_value = _normalize_apparel_fr_size(fields.fr_size)
    size_for_title = size_value.upper() if size_value else ""
    gender_value = _clean(fields.gender) or "femme"
    if fields.is_dress:
        item_label = "Robe"
        item_label_plural = "robes"
    elif fields.is_cardigan:
        item_label = "Gilet"
        item_label_plural = "gilets"
    else:
        item_label = "Pull"
        item_label_plural = "pulls"
    item_label_lower = item_label.lower()
    color = translate_color_to_french(fields.color_main)
    color = _clean(color)
    pattern_raw = _clean(fields.knit_pattern)
    pattern, neckline_value = split_neckline_from_pattern(pattern_raw)
    top_size_estimate = estimate_fr_top_size(
        fields.bust_flat_measurement_cm,
        length_measurement_cm=fields.length_measurement_cm,
    )
    estimated_size_label = (
        top_size_estimate.estimated_size if not fields.size_label_visible else None
    )
    estimated_size_note = top_size_estimate.note if not fields.size_label_visible else None
    estimated_size_primary = (
        _extract_primary_size_label(estimated_size_label) if estimated_size_label else None
    )
    length_descriptor = top_size_estimate.length_descriptor
    bust_flat_display = _format_measurement(fields.bust_flat_measurement_cm)
    length_display = _format_measurement(fields.length_measurement_cm)
    sku = (fields.sku or "").strip()
    sku_display = sku if sku else "SKU/nc"

    cotton_percent = _ensure_percent(fields.cotton_pct) if fields.cotton_pct else ""
    cotton_value = fields.cotton_percentage_value
    size_label_missing = not fields.size_label_visible
    composition_label_unavailable = (not fields.fabric_label_visible) or fields.fabric_label_cut
    size_label_cut_message = "Étiquette taille coupée pour plus de confort."
    composition_label_cut_message = "Étiquette composition coupée pour plus de confort."
    combined_label_cut_message = "Étiquette taille et compos coupées pour plus de confort."

    material_segment = ""
    pattern_lower = pattern.lower() if pattern else ""
    pattern_normalized = (
        _normalize_text_for_comparison(pattern_lower) if pattern_lower else ""
    )
    rule = _find_pattern_rule(pattern_normalized)
    if fields.has_cashmere:
        material_segment = "en cachemire"
    elif fields.has_wool:
        material_segment = "en laine"
    elif cotton_percent:
        if cotton_value is not None and cotton_value >= 60:
            material_segment = f"{cotton_percent} coton"
        else:
            material_segment = "coton"
    elif fields.fabric_label_visible and fields.cotton_pct:
        material_segment = "coton"

    if rule and rule.material_override:
        if rule.material_override == "en laine torsadée":
            if fields.has_wool:
                material_segment = rule.material_override
        else:
            material_segment = rule.material_override

    color_tokens: List[str] = []
    if color:
        color_tokens.append(color)
    if pattern:
        pattern_already_in_material = _contains_normalized_phrase(
            material_segment, pattern
        )
        if not pattern_already_in_material:
            color_tokens.append(pattern)
        elif not color_tokens:
            color_tokens.append(pattern)
    color_phrase = " ".join(token for token in color_tokens if token)

    title_parts = [f"{item_label} Tommy Hilfiger femme"]
    if fields.size_label_visible and (size_for_title or size_value):
        title_parts.append(f"taille {size_for_title or size_value}")
    elif estimated_size_label:
        title_parts.append(
            f"taille {estimated_size_primary or estimated_size_label}"
        )
    elif size_value:
        title_parts.append(f"taille {size_value}")
    if material_segment:
        title_parts.append(material_segment)
    if color_phrase:
        title_parts.append(color_phrase)
    if neckline_value:
        title_parts.append(neckline_value)
    if fields.made_in_europe:
        title_parts.append("Made in Europe")
    title_parts.extend(["-", sku_display])
    title = " ".join(part for part in title_parts if part).replace("  ", " ").strip()

    bust_measurement_used = (
        not fields.size_label_visible
        and fields.bust_flat_measurement_cm is not None
        and fields.bust_flat_measurement_cm > 0
    )
    length_measurement_used = (
        not fields.size_label_visible
        and length_descriptor is not None
        and fields.length_measurement_cm is not None
        and fields.length_measurement_cm > 0
    )

    size_measurement_details: List[str] = []
    if bust_measurement_used and not estimated_size_note:
        bust_circumference_display = _format_measurement(
            fields.bust_flat_measurement_cm * 2 if fields.bust_flat_measurement_cm else None
        )
        if bust_circumference_display:
            size_measurement_details.append(f"{bust_circumference_display} de poitrine")
    if length_measurement_used and length_display:
        size_measurement_details.append(f"longueur épaule-ourlet {length_display}")

    size_measurement_suffix = (
        f" ({', '.join(size_measurement_details)})" if size_measurement_details else ""
    )

    if fields.size_label_visible and (size_for_title or size_value):
        size_sentence = size_for_title or size_value
        if size_measurement_suffix:
            first_sentence = (
                f"{item_label} Tommy Hilfiger pour {gender_value} taille {size_sentence}{size_measurement_suffix}."
            )
        else:
            first_sentence = (
                f"{item_label} Tommy Hilfiger pour {gender_value} taille {size_sentence}."
            )
    elif estimated_size_label:
        size_sentence = estimated_size_primary or estimated_size_label
        estimated_details: List[str] = []
        if estimated_size_note:
            estimated_details.append(estimated_size_note)
        if size_measurement_details:
            estimated_details.extend(size_measurement_details)

        first_sentence = (
            f"{item_label} Tommy Hilfiger pour {gender_value} taille {size_sentence}"
        )
        if estimated_details:
            joined_details = " ".join(detail.strip() for detail in estimated_details)
            first_sentence = f"{first_sentence} ({joined_details})"
        if not first_sentence.endswith("."):
            first_sentence = f"{first_sentence}."
    elif size_value:
        size_sentence = size_value
        first_sentence = (
            f"{item_label} Tommy Hilfiger pour {gender_value} taille {size_value}{size_measurement_suffix}."
        )
    else:
        size_sentence = "non précisée"
        first_sentence = (
            f"{item_label} Tommy Hilfiger pour {gender_value} taille non précisée{size_measurement_suffix}."
        )

    pattern_sentence_value = pattern.lower() if pattern else ""
    style_segments: List[str] = []
    pattern_segment = ""
    if rule:
        pattern_segment = rule.style.format(
            pattern=pattern_sentence_value,
            color=color,
            item_label=item_label,
            item_label_lower=item_label_lower,
        ).strip()
    elif pattern and color:
        pattern_segment = (
            f"Motif {pattern_sentence_value} sur un coloris {color} facile à associer."
        )
    elif pattern:
        pattern_segment = (
            f"Motif {pattern_sentence_value} mis en valeur, se référer aux photos pour les nuances."
        )

    if pattern_segment:
        style_segments.append(pattern_segment)
    else:
        if color:
            style_segments.append(
                f"Coloris {color} facile à associer pour un look intemporel."
            )
        else:
            style_segments.append(
                "Coloris non précisé, se référer aux photos pour les nuances."
            )

    if neckline_value:
        neckline_sentence = (
            f"{neckline_value[0].upper() + neckline_value[1:]} qui structure joliment l'encolure."
        )
        style_segments.append(neckline_sentence)

    # Longueur et manches ne sont plus rappelées ici pour éviter les répétitions.

    style_sentence = " ".join(style_segments).strip()

    def build_composition_sentence() -> str:
        if composition_label_unavailable:
            if size_label_missing:
                return combined_label_cut_message
            return composition_label_cut_message

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
        _append_material(fields.polyamide_pct, fields.has_polyamide, "polyamide")
        _append_material(fields.nylon_pct, fields.has_nylon, "nylon")
        _append_material(fields.elastane_pct, fields.has_elastane, "élasthanne")

        if parts:
            return f"Composition : {_join_fibers(parts)}."
        return "Composition non lisible sur l'étiquette (voir photos pour confirmation)."

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

    first_paragraph_lines: List[str] = [first_sentence]
    if estimated_size_note and not estimated_size_label:
        first_paragraph_lines.append(estimated_size_note)
    if style_sentence:
        first_paragraph_lines.append(style_sentence)

    marketing_highlight = build_tommy_marketing_highlight(fields, pattern_raw)

    second_paragraph_lines = [marketing_highlight, composition_sentence]
    if made_in_sentence:
        second_paragraph_lines.append(made_in_sentence)

    third_paragraph_lines: List[str] = []
    if defects:
        third_paragraph_lines.append(f"Très bon état : {defects} (voir photos)")
    else:
        third_paragraph_lines.append("Très bon état")

    label_notice: Optional[str] = None
    if size_label_missing and not composition_label_unavailable:
        label_notice = size_label_cut_message
    elif size_label_missing and composition_label_unavailable:
        if composition_sentence.strip() != combined_label_cut_message:
            label_notice = combined_label_cut_message
    elif composition_label_unavailable:
        if composition_sentence.strip() not in (
            composition_label_cut_message,
            combined_label_cut_message,
        ):
            label_notice = composition_label_cut_message

    if label_notice:
        existing_lines = second_paragraph_lines + third_paragraph_lines
        if not any(label_notice == line.strip() for line in existing_lines):
            third_paragraph_lines.append(label_notice)

    third_paragraph_lines.extend(
        [
            "📏 Mesures détaillées visibles en photo pour plus de précisions.",
            "📦 Envoi rapide et soigné",
        ]
    )

    estimated_size_for_hashtag = None
    if estimated_size_label:
        estimated_size_for_hashtag = (
            estimated_size_primary or estimated_size_label
        )
    size_reference_for_hashtag = (
        size_for_title or size_value or estimated_size_for_hashtag or estimated_size_label
    )
    size_hashtag = _normalize_size_hashtag(size_reference_for_hashtag)

    fourth_paragraph_lines = [
        f"✨ Retrouvez tous mes {item_label_plural} Tommy femme ici 👉 #durin31tf{size_hashtag}",
        "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !",
    ]

    hashtags: List[str] = []

    def add_hashtag(tag: str) -> None:
        tag_clean = tag.strip()
        if tag_clean and tag_clean not in hashtags:
            hashtags.append(tag_clean)

    add_hashtag("#tommyhilfiger")
    add_hashtag(f"#{item_label_lower}tommy")
    add_hashtag("#tommy")
    add_hashtag(f"#{item_label_lower}femme")
    add_hashtag("#modefemme")
    add_hashtag("#preloved")
    add_hashtag(f"#durin31tf{size_hashtag}")
    add_hashtag("#ptf")

    if rule:
        for tag_template in rule.hashtags:
            add_hashtag(tag_template.format(item_label_lower=item_label_lower))

    if cotton_value is not None and cotton_value > 0:
        add_hashtag(f"#{item_label_lower}coton")
    if fields.has_wool:
        add_hashtag(f"#{item_label_lower}laine")
    if fields.has_cashmere:
        add_hashtag(f"#{item_label_lower}cachemire")
    if pattern_lower:
        if "marini" in pattern_lower:
            add_hashtag("#mariniere")
        if "torsad" in pattern_lower:
            add_hashtag(f"#{item_label_lower}torsade")
    if color:
        primary_color = color.split()[0].lower()
        add_hashtag(f"#{item_label_lower}{primary_color}")

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
                    - Matière = {{cotton_pct}}% coton (+ {{polyester_pct}}% polyester si présent, + {{polyamide_pct}}% polyamide si présent, + {{elastane_pct}}% élasthanne si présent)
                    - Genre = {{gender}}  (valeurs attendues : femme, homme, mix)
                    - Tâches et défauts = Ce qui doit impérativement apparaître dans l'annonce si identifié sur photos ou fournit en commentaire {{defects}}
                    - SKU = {{sku}} (utilise JLF + numéro (1 à 3 chiffres) ;
                      reprends exactement le numéro présent sur l’étiquette blanche visible sur le jean)

                    Utilise ce format :
                    TITRE
                    Jean Levi’s {{model}} FR{{fr_size}} W{{w}} L{{l}} coupe {{fit_leg}} {{cotton_pct}}% coton {{gender}} {{color_main}} - {{sku}}
                    
                    DESCRIPTION + HASHTAG
                    Jean Levi’s modèle {{model}} pour {{gender}}.
                    Taille {{w}} US (équivalent {{fr_size}} FR), coupe {{fit_leg}} à taille {{rise_class}}, pour une silhouette ajustée et confortable.
                    Coloris {{color_main}} légèrement délavé, très polyvalent et facile à assortir.
                    Composition : {{cotton_pct}}% coton{{#if polyester_pct}}, {{polyester_pct}}% polyester{{/if}}{{#if polyamide_pct}}, {{polyamide_pct}}% polyamide{{/if}}{{#if elastane_pct}}, {{elastane_pct}}% élasthanne{{/if}} pour une touche de stretch et plus de confort.
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
                    - Composition = {{cotton_pct}}, {{wool_pct}}, {{cashmere_pct}}, {{polyester_pct}}, {{polyamide_pct}}, {{viscose_pct}}, {{elastane_pct}} telles qu'indiquées sur l'étiquette
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
                    Pull Tommy Hilfiger femme taille {{fr_size}} {{matiere_principale}} {{color_main}} {{knit_pattern}} {{made_in_europe}} - {{sku}}

                    DESCRIPTION + HASHTAG
                    Pull Tommy Hilfiger pour femme taille {{fr_size}}.
                    Coloris {{color_main}} {{knit_pattern}}, parfait pour un look intemporel.
                    Composition : {{cotton_pct}}% coton{{#if wool_pct}}, laine{{/if}}{{#if cashmere_pct}}, cachemire{{/if}}{{#if polyester_pct}}, {{polyester_pct}}% polyester{{/if}}{{#if polyamide_pct}}, {{polyamide_pct}}% polyamide{{/if}}{{#if viscose_pct}}, {{viscose_pct}}% viscose{{/if}}{{#if elastane_pct}}, {{elastane_pct}}% élasthanne{{/if}} (adapte selon l'étiquette visible).
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
