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
from typing import Callable, Dict, List, Optional, Tuple, Union

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


def _normalize_us_waist_label(value: Optional[str]) -> str:
    """Normalize US waist label strings (e.g. "W33", "33/32") to a numeric token."""

    cleaned = _clean(value)
    if not cleaned:
        return ""

    match = re.search(r"(?i)w\s*([0-9]{2,3})", cleaned)
    if match:
        return match.group(1)

    match = re.search(r"([0-9]{2,3})", cleaned)
    if match:
        return match.group(1)

    return cleaned


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
    return (
        normalized.startswith("taille estimée à partir du tour de taille")
        or normalized.startswith("taille estimée à partir d'un tour de taille")
        or normalized.startswith("taille estimée à partir de la largeur de taille")
    )


def _normalize_text_for_comparison(value: str) -> str:
    """Normalize text for accent-insensitive substring checks."""

    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


def _contains_normalized_phrase(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    return _normalize_text_for_comparison(needle) in _normalize_text_for_comparison(haystack)


_PREMIUM_COTTON_KEYWORDS = ("pima", "supima", "prima")


def _contains_premium_cotton_hint(value: Optional[str]) -> bool:
    if not value:
        return False
    normalized = _normalize_text_for_comparison(value)
    collapsed = re.sub(r"[^a-z0-9]+", "", normalized)
    return any(
        keyword in normalized or keyword in collapsed
        for keyword in _PREMIUM_COTTON_KEYWORDS
    )


def _has_premium_cotton_indicator(*values: Optional[str]) -> bool:
    """Return True when any provided field hints at Pima cotton."""

    return any(_contains_premium_cotton_hint(value) for value in values)


def _has_premium_cotton_indicator_anywhere(fields: ListingFields) -> bool:
    """Return True if any textual field on the listing hints at premium cotton.

    This acts as a safety net when the Pima / Supima mention is captured in a
    secondary field (e.g. logo note, user comment) instead of the usual
    feature_notes/technical_features slots.
    """

    for value in vars(fields).values():
        if isinstance(value, str) and _contains_premium_cotton_hint(value):
            return True
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str) and _contains_premium_cotton_hint(item):
                    return True
    return False


_POLYESTER_CONTRADICTION_KEYWORDS = tuple(
    _normalize_text_for_comparison(keyword)
    for keyword in (
        "coton",
        "cotton",
        "laine",
        "wool",
        "cachemire",
        "cashmere",
        "soie",
        "silk",
        "lin",
        "linen",
        "chanvre",
        "hemp",
        "viscose",
        "rayonne",
        "modal",
        "polyamide",
        "nylon",
        "acrylique",
        "acrylic",
        "elasthanne",
        "elastane",
        "spandex",
        "lycra",
    )
)


def _defects_contradict_polyester(text: Optional[str]) -> bool:
    if not text:
        return False
    normalized_text = _normalize_text_for_comparison(text)
    return any(keyword in normalized_text for keyword in _POLYESTER_CONTRADICTION_KEYWORDS)


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


def _parse_fr_size_value(fr_size: Optional[str]) -> Optional[int]:
    if not fr_size:
        return None
    match = re.search(r"(\d+)", str(fr_size))
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def _detect_stain_severity(defects: str) -> str:
    normalized = (defects or "").casefold()
    if not normalized:
        return "none"

    large_keywords = (
        "grosse tache",
        "grosses taches",
        "grosse tâche",
        "grosses tâches",
        "tache blanche",
        "tâche blanche",
        "taches blanches",
        "tâches blanches",
    )
    small_keywords = (
        "petite tache",
        "petites taches",
        "petite tâche",
        "petites tâches",
        "tache visible",
        "tache visibles",
        "tâche visible",
        "tâche visibles",
        "taches visibles",
        "tâches visibles",
        "micro tache",
        "micro tâche",
        "micro taches",
        "micro tâches",
        "tache",
        "taches",
        "taché",
        "tachée",
    )

    if any(keyword in normalized for keyword in large_keywords):
        return "large"
    if any(keyword in normalized for keyword in small_keywords):
        return "small"
    return "none"


def _is_premium_model(model: str) -> bool:
    return "premium" in (model or "").casefold()


def _estimate_price_for_jean_levis(
    *, model: str, fr_size_display: Optional[str], defects: str, color: str
) -> str:
    fr_size_value = _parse_fr_size_value(fr_size_display)
    stain_severity = _detect_stain_severity(defects)
    is_premium = _is_premium_model(model)
    is_white = "blanc" in (color or "").casefold()

    if is_premium:
        if stain_severity == "large" or (is_white and stain_severity != "none"):
            price = 14
        else:
            if fr_size_value == 46 and stain_severity != "none":
                price = 21
            else:
                base_price = 20 if stain_severity == "none" else 19
                if fr_size_value == 46 and stain_severity == "none":
                    price = base_price + 3
                else:
                    price = base_price
    else:
        if stain_severity != "none":
            price = 12 if is_white else 17
            if fr_size_value:
                if fr_size_value >= 50:
                    price = 22
                elif fr_size_value == 48:
                    price = 20
                elif fr_size_value == 46:
                    price = 19
        else:
            if fr_size_value:
                if fr_size_value >= 50:
                    price = 24
                elif fr_size_value == 48:
                    price = 22
                elif fr_size_value == 46:
                    price = 20
                else:
                    price = 19
            else:
                price = 19

    severity_label = {
        "none": "aucun défaut notable",
        "small": "défauts légers",
        "large": "défauts marqués",
    }.get(stain_severity, "défauts non précisés")

    size_label = f"taille FR {fr_size_display}" if fr_size_display else "taille non précisée"
    premium_label = "modèle premium" if is_premium else "modèle standard"
    color_label = "couleur blanche" if is_white else None

    criteria = [premium_label, size_label, severity_label]
    if color_label:
        criteria.append(color_label)

    criteria_display = ", ".join(criteria)
    return f"Estimation de prix indicative (critères : {criteria_display}) : {price}€"


@dataclass
class ListingTemplate:
    name: str
    description: str
    prompt: str
    render_callback: Callable[
        [ListingFields], Union[Tuple[str, str], Tuple[str, str, Optional[str]]]
    ]

    def render(self, fields: ListingFields) -> Tuple[str, str, Optional[str]]:
        result = self.render_callback(fields)
        if len(result) == 2:
            title, description = result  # type: ignore[misc]
            price_estimate = None
        else:
            title, description, price_estimate = result  # type: ignore[misc]
        return title, description, price_estimate


def render_template_jean_levis_femme(
    fields: ListingFields,
) -> Tuple[str, str, Optional[str]]:
    fit_title, fit_description, fit_hashtag = normalize_fit_terms(fields.fit_leg)
    waist_measurement_value = fields.waist_measurement_cm
    if (
        (waist_measurement_value is None or waist_measurement_value <= 0)
        and fields.waist_flat_measurement_cm is not None
        and fields.waist_flat_measurement_cm > 0
    ):
        waist_measurement_value = fields.waist_flat_measurement_cm

    measurement_fr = fr_size_from_waist_measurement(
        waist_measurement_value, ensure_even=True
    )

    size_note: Optional[str] = None
    size_estimated = False

    fr_candidate = _clean(fields.fr_size)
    us_candidate_raw = _clean(fields.us_w)
    us_candidate = _normalize_us_waist_label(us_candidate_raw)

    normalized_sizes: Optional[NormalizedSizes] = None
    if fields.size_label_visible or fr_candidate or us_candidate:
        normalized_sizes = normalize_sizes(
            fields.us_w,
            fields.fr_size,
            fields.has_elastane,
            ensure_even_fr=True,
            waist_measurement_cm=waist_measurement_value,
        )

    fr_display = fr_candidate or (normalized_sizes.fr_size if normalized_sizes else "")
    us_display = (
        normalized_sizes.us_size if normalized_sizes and normalized_sizes.us_size else None
    )
    if not us_display:
        us_display = us_candidate
    us_display_label = f"W{us_display}" if us_display else ""
    us_length_label = f"L{fields.us_l}" if fields.us_l else ""

    if normalized_sizes and fields.size_label_visible:
        size_note = normalized_sizes.note
        if _is_waist_measurement_note(size_note):
            size_estimated = True
            size_note = None

    if not fr_display and measurement_fr:
        fr_display = measurement_fr
        size_estimated = True

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
    elastane_pct_value: Optional[float] = None
    if fields.fabric_label_visible and fields.elastane_pct:
        elastane_pct_raw = str(fields.elastane_pct).strip().replace("%", "").replace(",", ".")
        if elastane_pct_raw:
            try:
                elastane_pct_value = float(elastane_pct_raw)
            except ValueError:
                elastane_pct_value = None
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

    size_label_cut_message = "Étiquette de taille coupée pour plus de confort."
    composition_label_cut_message = "Étiquette de composition coupée pour plus de confort."
    combined_label_cut_message = "Étiquettes de taille et composition coupées pour plus de confort."

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

    rise_normalized = rise.casefold()
    rise_is_low = (
        "basse" in rise_normalized or "low" in rise_normalized
        if rise_normalized
        else False
    )
    rise_is_high = (
        "haute" in rise_normalized or "high" in rise_normalized
        if rise_normalized
        else False
    )
    has_stretch = bool(elastane_pct_value and elastane_pct_value > 2)

    fit_normalized_for_flags = _normalize_text_for_comparison(
        fit_hashtag_source or fit_description_text
    )
    fit_is_fitted = any(
        keyword in fit_normalized_for_flags
        for keyword in (
            "slim",
            "skinny",
            "taper",
            "fus",
            "cigarette",
            "ajuste",
            "ajustee",
        )
    )

    color_flag_source = _clean(fields.color_main) or color or ""
    color_normalized_for_flags = _normalize_text_for_comparison(color_flag_source)

    detail_flag_source = " ".join(
        part
        for part in (
            _clean(fields.feature_notes),
            _clean(fields.technical_features),
            _clean(fields.special_logo),
        )
        if part
    )
    details_normalized_for_flags = _normalize_text_for_comparison(detail_flag_source)

    y2k_wash_hint = any(
        keyword in color_normalized_for_flags
        for keyword in ("clair", "delave", "delavage", "bleach", "stone", "acid")
    )
    y2k_silhouette_hint = any(
        keyword in fit_normalized_for_flags
        for keyword in ("bootcut", "flare", "evase", "wide", "baggy", "loose")
    )
    y2k_brand_logo_hint = bool(fields.special_logo) or any(
        keyword in details_normalized_for_flags for keyword in ("logo", "patch", "brode", "brodee")
    )
    y2k_color_hint = any(
        keyword in color_normalized_for_flags
        for keyword in (
            "rose",
            "violet",
            "lila",
            "jaune",
            "orange",
            "turquoise",
            "fuchsia",
            "pastel",
            "flashy",
            "vert clair",
            "bleu clair",
        )
    )
    y2k_detail_hint = any(
        keyword in details_normalized_for_flags
        for keyword in (
            "strass",
            "paillet",
            "brillant",
            "metal",
            "metalise",
            "surpiqu",
            "contrast",
        )
    )

    y2k_hint_count = sum(
        (1 if flag else 0)
        for flag in (
            y2k_wash_hint,
            y2k_silhouette_hint,
            y2k_brand_logo_hint,
            y2k_color_hint,
            y2k_detail_hint,
        )
    )

    has_y2k_vibe = rise_is_low or (has_stretch and fit_is_fitted) or y2k_hint_count >= 3

    title_intro = "Jean Levi’s"
    if model:
        title_intro = f"{title_intro} {model}"

    cotton_title_segment = f"{cotton} coton" if cotton else ""
    title_parts: List[str] = [title_intro]
    if fr_display:
        title_parts.append(f"FR{fr_display}")
    if us_display_label:
        title_parts.append(us_display_label)
    if us_length_label:
        title_parts.append(us_length_label)
    if fit_title_text:
        title_parts.extend(["coupe", fit_title_text])
    if rise_is_low:
        title_parts.append("taille basse")
    if has_stretch:
        title_parts.append("stretch")
    if cotton_title_segment:
        title_parts.append(cotton_title_segment)
    if gender_value:
        title_parts.append(gender_value)
    if color:
        title_parts.append(color)
    title_parts.extend(["-", sku_display])
    title = " ".join(part for part in title_parts if part).replace("  ", " ").strip()

    us_sentence_label = " ".join(
        part for part in (us_display_label, us_length_label) if part
    ).strip()
    fit_phrase = fit_description_text or "non précisée"
    if rise_is_low:
        rise_phrase = "basse"
    elif rise_is_high:
        rise_phrase = "haute"
    elif rise:
        rise_phrase = rise
    else:
        rise_phrase = "moyenne"

    rise_label = f"taille {rise_phrase}"
    rise_label_english = "mid rise"
    if rise_is_low:
        rise_label_english = "low rise"
    elif rise_is_high:
        rise_label_english = "high rise"
    elif "moy" not in rise_phrase.lower():
        rise_label_english = "mid rise"

    rise_measured_from_photo = bool(fields.rise_measurement_cm and not fields.rise_class)

    if fr_display:
        fr_size_sentence = f"Taille {fr_display} FR"
    elif us_sentence_label:
        fr_size_sentence = f"Taille {us_sentence_label} US"
    else:
        fr_size_sentence = "Taille non précisée"
    if size_estimated:
        fr_size_sentence = f"{fr_size_sentence} (voir photos)"
    fr_size_sentence = f"{fr_size_sentence}."

    rise_fit_sentence = (
        f"{rise_label_english}/{rise_label} coupe {fit_phrase}, pour une silhouette ajustée et confortable."
    )
    rise_measurement_note: Optional[str] = None
    if rise_measured_from_photo:
        rise_measurement_note = "Hauteur de taille déduite de la mesure en cm visible en photo."
    us_size_sentence: Optional[str] = None
    if us_sentence_label and fr_display:
        us_size_sentence = f"Équivalent US {us_sentence_label}."

    gender_label = gender_value or "femme"
    model_segment = f" {model}" if model else ""
    intro_sentence_parts = [
        f"Jean Levi’s{model_segment} en {rise_label} denim pour {gender_label}",
        "— parfait look Y2K" if has_y2k_vibe else None,
    ]
    intro_sentence = " ".join(part for part in intro_sentence_parts if part).replace(
        "  ", " "
    ).rstrip(".") + "."

    cta_sentence = (
        "Disponible immédiatement — envoi rapide 🚚 / Ajoutez aux favoris si vous hésitez encore ✨"
    )

    first_paragraph_lines = [intro_sentence, fr_size_sentence, rise_fit_sentence]
    if rise_measurement_note:
        first_paragraph_lines.append(rise_measurement_note)
    if us_size_sentence:
        first_paragraph_lines.append(us_size_sentence)
    first_paragraph_lines.append(cta_sentence)
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
        third_paragraph_lines.append(
            f"Bon état général. Légères traces d’usage discrètes : {defects} (voir photos)."
        )
    else:
        third_paragraph_lines.append("Très bon état général.")

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
        f"#levis{model}" if model else "",
        "#levis",
        "#jeanlevis",
        "#jeandenim",
        f"#{fit_hashtag_text}jean" if fit_hashtag_text else "",
        "#lowrise" if rise_is_low else "",
        "#taillebasse" if rise_is_low else "",
        "#highwaist" if rise_is_high else "",
        f"#stretch" if has_stretch else "",
        "#y2k" if has_y2k_vibe else "",
        f"#w{us_display.lower()}" if us_display else "",
        f"#l{fields.us_l.lower()}" if fields.us_l else "",
        f"#fr{fr_display.lower()}" if fr_display else "",
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

    price_estimate = _estimate_price_for_jean_levis(
        model=model,
        fr_size_display=fr_display,
        defects=defects,
        color=color,
    )

    return title, description, price_estimate


@dataclass(frozen=True)
class PatternRule:
    tokens: Tuple[str, ...]
    marketing: str
    style: str
    hashtags: Tuple[str, ...]
    material_override: Optional[str] = None


@dataclass(frozen=True)
class PolaireBrandRule:
    keywords: Tuple[str, ...]
    display: str
    hashtag: str
    short_code: str


_POLAIRE_BRAND_RULES: Tuple[PolaireBrandRule, ...] = (
    PolaireBrandRule(
        keywords=("thenorthface", "north face", "the north face", "tnf"),
        display="The North Face",
        hashtag="#thenorthface",
        short_code="tnf",
    ),
    PolaireBrandRule(
        keywords=("columbia",),
        display="Columbia",
        hashtag="#columbia",
        short_code="col",
    ),
)


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


def _resolve_polaire_brand(fields: ListingFields) -> Tuple[str, str, str]:
    sku_value = (fields.sku or "").strip().upper()
    if sku_value.startswith("PTNF"):
        return "The North Face", "#thenorthface", "tnf"
    if sku_value.startswith("PC"):
        return "Columbia", "#columbia", "col"

    candidates = [fields.brand, fields.model]
    for candidate in candidates:
        if not candidate:
            continue
        normalized_candidate = _normalize_text_for_comparison(candidate)
        if not normalized_candidate:
            continue
        for spec in _POLAIRE_BRAND_RULES:
            if any(keyword in normalized_candidate for keyword in spec.keywords):
                return spec.display, spec.hashtag, spec.short_code

    fallback_display = _clean(fields.brand) or "Polaire"
    fallback_hashtag = "#polaireoutdoor"
    return fallback_display, fallback_hashtag, "polaire"


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
        top_size_estimate.estimated_size
        if (not fields.size_label_visible or not size_value)
        else None
    )
    estimated_size_primary = (
        _extract_primary_size_label(estimated_size_label) if estimated_size_label else None
    )
    estimated_size_note = (
        top_size_estimate.note
        if (not fields.size_label_visible or not size_value)
        else None
    )
    if not estimated_size_note and estimated_size_primary:
        estimated_size_note = (
            f"Taille {estimated_size_primary}, estimée à la main à partir des mesures à plat (voir photos)."
        )
    size_for_title = size_for_title or estimated_size_primary or estimated_size_label or ""
    length_descriptor = top_size_estimate.length_descriptor
    sku = (fields.sku or "").strip()
    sku_display = sku if sku else "SKU/nc"

    cotton_percent = _ensure_percent(fields.cotton_pct) if fields.cotton_pct else ""
    cotton_value = fields.cotton_percentage_value
    size_label_missing = not fields.size_label_visible
    composition_label_unavailable = (not fields.fabric_label_visible) or fields.fabric_label_cut
    size_label_cut_message = "Étiquette de taille coupée pour plus de confort."
    composition_label_cut_message = "Étiquette de composition coupée pour plus de confort."
    combined_label_cut_message = "Étiquettes de taille et composition coupées pour plus de confort."

    def build_measurement_note() -> Optional[str]:
        if fields.bust_flat_measurement_cm is None:
            return None
        try:
            bust_value = float(fields.bust_flat_measurement_cm)
        except (TypeError, ValueError):
            return None
        if bust_value <= 0:
            return None

        bust_note = "Taille estimée à la main à partir des mesures à plat (voir photos)"

        notes = [bust_note]
        if fields.length_measurement_cm:
            length_display = int(round(fields.length_measurement_cm))
            notes.append(f"longueur épaule-ourlet ~{length_display} cm")

        return ". ".join(notes)

    measurement_note = build_measurement_note() if size_label_missing else None

    premium_cotton = _has_premium_cotton_indicator(
        fields.cotton_pct,
        fields.knit_pattern,
        fields.defects,
        fields.model,
        fields.color_main,
        fields.feature_notes,
        fields.technical_features,
        fields.made_in,
    )
    if not premium_cotton:
        premium_cotton = _has_premium_cotton_indicator_anywhere(fields)

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
        cotton_label = "coton premium" if premium_cotton else "coton"
        if cotton_value is not None and cotton_value >= 60:
            material_segment = f"{cotton_percent} {cotton_label}"
        else:
            material_segment = cotton_label
    elif fields.fabric_label_visible and fields.cotton_pct:
        material_segment = "coton premium" if premium_cotton else "coton"

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

    brand_segment = "Tommy Hilfiger premium femme" if premium_cotton else "Tommy Hilfiger femme"
    title_parts = [f"{item_label} {brand_segment}"]
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

    if fields.size_label_visible and (size_for_title or size_value):
        size_sentence = size_for_title or size_value
        first_sentence = (
            f"{item_label} Tommy Hilfiger pour {gender_value} taille {size_sentence}."
        )
    elif estimated_size_label:
        size_sentence = estimated_size_primary or estimated_size_label
        if measurement_note:
            first_sentence = (
                f"{item_label} Tommy Hilfiger pour {gender_value} taille {size_sentence} "
                f"({measurement_note})."
            )
            estimated_size_note = None
        else:
            first_sentence = (
                f"{item_label} Tommy Hilfiger pour {gender_value} taille {size_sentence}."
            )
    elif size_value:
        size_sentence = size_value
        first_sentence = (
            f"{item_label} Tommy Hilfiger pour {gender_value} taille {size_value}."
        )
    else:
        size_sentence = "non précisée"
        first_sentence = (
            f"{item_label} Tommy Hilfiger pour {gender_value} taille non précisée."
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
    if estimated_size_label and estimated_size_note:
        first_paragraph_lines.append(estimated_size_note)
    elif estimated_size_note and not estimated_size_label:
        first_paragraph_lines.append(estimated_size_note)
    if style_sentence:
        first_paragraph_lines.append(style_sentence)

    marketing_highlight = build_tommy_marketing_highlight(fields, pattern_raw)

    second_paragraph_lines = [marketing_highlight]
    if premium_cotton:
        second_paragraph_lines.append(
            "Coton de qualité premium pour un toucher délicat."
        )
    second_paragraph_lines.append(composition_sentence)
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


def render_template_polaire_outdoor(fields: ListingFields) -> Tuple[str, str]:
    size_value = _normalize_apparel_fr_size(fields.fr_size)
    size_for_title = size_value.upper() if size_value else ""
    gender_value = _clean(fields.gender) or "femme"
    brand_display, brand_hashtag, brand_short_code = _resolve_polaire_brand(fields)
    color = translate_color_to_french(fields.color_main)
    color = _clean(color)
    zip_style_value = _clean(fields.zip_style)
    neckline_style_value = _clean(fields.neckline_style)
    special_logo_value = _clean(fields.special_logo)
    feature_notes = _clean(fields.feature_notes)
    technical_features = _clean(fields.technical_features)
    sku = (fields.sku or "").strip()
    sku_display = sku if sku else "SKU/nc"
    defects_original_text = (fields.defects or "").strip()

    top_size_estimate = estimate_fr_top_size(
        fields.bust_flat_measurement_cm,
        length_measurement_cm=fields.length_measurement_cm,
        measurement_profile="polaire_pull",
    )
    estimated_size_label = (
        top_size_estimate.estimated_size
        if (not fields.size_label_visible or not size_value)
        else None
    )
    estimated_size_primary = (
        _extract_primary_size_label(estimated_size_label) if estimated_size_label else None
    )
    estimated_size_note = (
        top_size_estimate.note
        if (not fields.size_label_visible or not size_value)
        else None
    )
    if not estimated_size_note and estimated_size_primary:
        estimated_size_note = (
            f"Taille {estimated_size_primary}, estimée à la main à partir des mesures à plat (voir photos)."
        )
    size_for_title = size_for_title or estimated_size_primary or estimated_size_label or ""
    length_descriptor = top_size_estimate.length_descriptor

    size_label_missing = not fields.size_label_visible
    composition_label_missing = not fields.fabric_label_visible
    fabric_label_cut = fields.fabric_label_cut
    size_label_missing_message = "Étiquette de taille non visible sur les photos."
    composition_label_missing_message = "Étiquette de composition non visible sur les photos."
    composition_label_cut_message = "Étiquette de composition coupée pour plus de confort."
    combined_label_missing_message = "Étiquettes coupées pour plus de confort."
    combined_label_cut_message = (
        "Étiquettes de taille et composition coupées pour plus de confort."
    )

    should_assume_polyester = (
        not fields.fabric_label_visible
        and not _defects_contradict_polyester(defects_original_text)
    )

    cotton_percent = _ensure_percent(fields.cotton_pct) if fields.cotton_pct else ""
    polyester_value = _ensure_percent(fields.polyester_pct) if fields.polyester_pct else ""
    viscose_value = _ensure_percent(fields.viscose_pct) if fields.viscose_pct else ""
    elastane_value = _ensure_percent(fields.elastane_pct) if fields.elastane_pct else ""
    polyamide_value = _ensure_percent(fields.polyamide_pct) if fields.polyamide_pct else ""
    wool_value = _ensure_percent(fields.wool_pct) if fields.wool_pct else ""
    cashmere_value = _ensure_percent(fields.cashmere_pct) if fields.cashmere_pct else ""
    nylon_value = _ensure_percent(fields.nylon_pct) if fields.nylon_pct else ""
    acrylic_value = _ensure_percent(fields.acrylic_pct) if fields.acrylic_pct else ""

    composition_parts: List[str] = []
    if fields.fabric_label_visible:
        if cotton_percent:
            composition_parts.append(f"{cotton_percent} coton")
        if fields.has_wool:
            composition_parts.append(wool_value + " laine" if wool_value else "laine")
        if fields.has_cashmere:
            composition_parts.append(
                cashmere_value + " cachemire" if cashmere_value else "cachemire"
            )
        if polyester_value:
            composition_parts.append(f"{polyester_value} polyester")
        if polyamide_value:
            composition_parts.append(f"{polyamide_value} polyamide")
        if viscose_value:
            composition_parts.append(f"{viscose_value} viscose")
        if nylon_value:
            composition_parts.append(f"{nylon_value} nylon")
        if elastane_value:
            composition_parts.append(f"{elastane_value} élasthanne")
        if acrylic_value:
            composition_parts.append(f"{acrylic_value} acrylique")

    composition_sentence: str
    if composition_parts:
        composition_sentence = f"Composition : {_join_fibers(composition_parts)}."
    elif should_assume_polyester:
        composition_sentence = "Composition : 100% polyester"
    elif fabric_label_cut:
        if size_label_missing:
            composition_sentence = combined_label_cut_message
        else:
            composition_sentence = composition_label_cut_message
    elif composition_label_missing:
        if size_label_missing:
            composition_sentence = combined_label_missing_message
        else:
            composition_sentence = composition_label_missing_message
    else:
        composition_sentence = "Composition non lisible sur l'étiquette (voir photos pour confirmation)."

    def _material_segment_for_title() -> str:
        if fields.has_cashmere:
            return "en cachemire"
        if fields.has_wool:
            return "en laine"
        cotton_value = fields.cotton_percentage_value
        if cotton_value is not None and cotton_value > 0:
            return "en coton"
        return ""

    material_segment = _material_segment_for_title()

    title_parts = [f"Polaire fleece {brand_display}"]
    if gender_value:
        title_parts.append(gender_value)
    if fields.size_label_visible and (size_for_title or size_value):
        title_parts.append(f"taille {size_for_title or size_value}")
    elif estimated_size_label:
        title_parts.append(f"taille {estimated_size_primary or estimated_size_label}")
    elif size_value:
        title_parts.append(f"taille {size_value}")
    if zip_style_value:
        title_parts.append(zip_style_value)
    if neckline_style_value:
        title_parts.append(neckline_style_value)
    if fields.has_hood:
        title_parts.append("capuche")
    if material_segment:
        title_parts.append(material_segment)
    if color:
        title_parts.append(color)
    if special_logo_value:
        title_parts.append(special_logo_value)
    title_parts.extend(["-", sku_display])
    title = " ".join(part for part in title_parts if part).replace("  ", " ").strip()

    first_paragraph_lines: List[str] = []
    audience_label = gender_value or "femme"
    intro_parts = ["Polaire fleece", brand_display, "pour", audience_label]
    first_paragraph_lines.append(" ".join(part for part in intro_parts if part).strip() + ".")
    if fields.size_label_visible and size_value:
        first_paragraph_lines.append(f"Taille FR {size_value}.")
    elif estimated_size_label:
        if estimated_size_note:
            first_paragraph_lines.append(estimated_size_note)
        else:
            first_paragraph_lines.append(
                f"Taille {estimated_size_primary or estimated_size_label}, estimée à la main à partir des mesures à plat (voir photos)."
            )
    elif estimated_size_note:
        first_paragraph_lines.append(estimated_size_note)
    style_tokens: List[str] = []
    if color:
        style_tokens.append(f"Coloris {color}")
    if zip_style_value:
        style_tokens.append(zip_style_value)
    if fields.has_hood:
        style_tokens.append("capuche protectrice")
    if neckline_style_value:
        style_tokens.append(neckline_style_value)
    if special_logo_value:
        normalized_logo_value = special_logo_value
        if "logo" not in normalized_logo_value.lower():
            normalized_logo_value = f"logo {normalized_logo_value}"
        style_tokens.append(normalized_logo_value)
    if style_tokens:
        first_paragraph_lines.append(", ".join(style_tokens) + ".")

    marketing_lines: List[str] = []
    length_sentence = (
        f"Coupe {length_descriptor} confortable." if length_descriptor else "Coupe cosy et respirante."
    )
    marketing_lines.append(length_sentence)
    if feature_notes:
        marketing_lines.append(feature_notes)
    if technical_features:
        marketing_lines.append(technical_features)
    if special_logo_value and "logo" not in special_logo_value.lower():
        marketing_lines.append(f"Détail signature : {special_logo_value}.")
    if fields.made_in_europe:
        marketing_lines.append("Mention Made in Europe confirmée.")
    marketing_lines.append(composition_sentence)

    defect_texts = get_defect_descriptions(fields.defect_tags)
    raw_defects = (fields.defects or "").strip()
    positive_state_aliases = {"très bon état", "très bon état général"}
    positive_state_aliases_casefold = {alias.casefold() for alias in positive_state_aliases}
    if raw_defects.casefold() in positive_state_aliases_casefold:
        raw_defects = ""
    if defect_texts:
        defects = ", ".join(defect_texts)
    else:
        defects = raw_defects if raw_defects else ""

    third_paragraph_lines: List[str] = []
    if defects:
        third_paragraph_lines.append(f"Très bon état : {defects} (voir photos)")
    else:
        third_paragraph_lines.append("Très bon état")

    label_notice: Optional[str] = None
    composition_sentence_clean = composition_sentence.strip()
    if size_label_missing and not fabric_label_cut and not composition_label_missing:
        label_notice = size_label_missing_message
    elif size_label_missing and fabric_label_cut:
        if composition_sentence_clean != combined_label_cut_message:
            label_notice = combined_label_cut_message
    elif size_label_missing and composition_label_missing:
        if composition_sentence_clean != combined_label_missing_message:
            label_notice = combined_label_missing_message
    elif fabric_label_cut:
        if composition_sentence_clean != composition_label_cut_message:
            label_notice = composition_label_cut_message
    elif composition_label_missing:
        if composition_sentence_clean != composition_label_missing_message:
            label_notice = composition_label_missing_message

    if label_notice:
        existing_lines = marketing_lines + third_paragraph_lines
        if not any(label_notice == line.strip() for line in existing_lines):
            third_paragraph_lines.append(label_notice)

    third_paragraph_lines.extend(
        [
            "📏 Mesures détaillées visibles en photo pour valider l'ajustement.",
            "📦 Envoi rapide et soigné",
        ]
    )

    size_reference_for_hashtag = (
        size_for_title
        or size_value
        or estimated_size_primary
        or estimated_size_label
        or "M"
    )
    size_hashtag = _normalize_size_hashtag(size_reference_for_hashtag)

    gender_token = "f"
    gender_lower = gender_value.lower()
    if "hom" in gender_lower:
        gender_token = "h"
    elif "mix" in gender_lower or "unisexe" in gender_lower:
        gender_token = "u"

    gender_size_hashtag = f"#durin31{gender_token}{size_hashtag}"

    fourth_paragraph_lines = [
        f"✨ Retrouvez toutes mes polaires {brand_display} ici 👉 #durin31{brand_short_code}{size_hashtag}",
        "",
        f"👀 Filtrez toutes mes pièces {audience_label} taille {size_hashtag} (polaire, pull, jacket…) 👉 {gender_size_hashtag}",
        "",
        "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !",
    ]

    hashtags: List[str] = []

    def add_hashtag(tag: str) -> None:
        tag_clean = tag.strip()
        if tag_clean and tag_clean not in hashtags:
            hashtags.append(tag_clean)

    gender_hashtag_map = {
        "femme": "#polairefemme",
        "homme": "#polairehomme",
    }
    gender_hashtag = gender_hashtag_map.get(gender_value.lower(), "#polairemixte")

    add_hashtag(brand_hashtag)
    add_hashtag(gender_hashtag)
    add_hashtag("#outdoor")
    add_hashtag("#randonnée")
    add_hashtag("#preloved")
    add_hashtag(f"#durin31{brand_short_code}{size_hashtag}")
    add_hashtag(gender_size_hashtag)
    if zip_style_value:
        zip_token = "#" + zip_style_value.replace(" ", "").replace("/", "")
        add_hashtag(zip_token.lower())
    if color:
        add_hashtag(f"#polaire{color.split()[0].lower()}")
    if material_segment:
        add_hashtag("#matierepremium")

    fallback_tags = ["#layering", "#polaire", "#secondevie"]
    for tag in fallback_tags:
        if len(hashtags) >= 10:
            break
        add_hashtag(tag)

    hashtags_tokens = hashtags[:10]
    hashtags_paragraph_lines = [" ".join(hashtags_tokens)]

    description = "\n\n".join(
        [
            "\n".join(first_paragraph_lines),
            "\n".join(marketing_lines),
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
                    - Commentaire (prioritaire) = informations utilisateur (taille, coupe, défauts, préférences) à appliquer en priorité dans l'estimation de prix, le titre et la description, même si elles ne sont pas visibles sur les photos {{defects}}
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
                    - Détail matière (ex : Pima / Supima) = {{feature_notes}} (recopie toute mention premium lisible sur l'étiquette)
                    - Composition = {{cotton_pct}}, {{wool_pct}}, {{cashmere_pct}}, {{polyester_pct}}, {{polyamide_pct}}, {{viscose_pct}}, {{elastane_pct}} telles qu'indiquées sur l'étiquette
                    - Made in = {{made_in}} (copie exactement la mention écrite)
                    - Défauts = {{defects}} (détaille chaque imperfection visible)
                    - SKU = {{sku}} (utilise PTF + numéro (1 à 3 chiffres) lorsque l'étiquette blanche est lisible)
                    - {{matiere_principale}} = synthèse des matières dominantes (ex : 100% coton, laine torsadée, cachemire)
                    - {{made_in_europe}} = écris « Made in Europe » uniquement si l'étiquette indique un pays européen, sinon laisse vide
                    - Commentaire (prioritaire) = applique en priorité toute information saisie par l'utilisateur (taille, matière, défaut, coupe) pour remplir les champs, calculer l'estimation de prix et rédiger l'annonce, même si le détail n'est pas visible sur les photos

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
            "template-polaire-outdoor": ListingTemplate(
                name="template-polaire-outdoor",
                description="Template polaire outdoor (The North Face / Columbia)",
                prompt=dedent(
                    """
                    Prend en considération cette légende :
                    - Marque = {{brand}} (The North Face ou Columbia, laisse vide si incertain)
                    - Modèle = {{model}} (nom exact ou référence)
                    - Taille = {{fr_size}} (XS/S/M/L/XL...), {{bust_flat_measurement_cm}}/{{length_measurement_cm}}/{{sleeve_measurement_cm}}/{{shoulder_measurement_cm}}/{{waist_flat_measurement_cm}}/{{hem_flat_measurement_cm}} en cm lorsque visibles
                    - Genre = {{gender}} (femme, homme, mix)
                    - Couleur principale = {{color_main}}
                    - Type de zip = {{zip_style}} (full zip, 1/4 zip, 1/2 zip, boutons…)
                    - Type de col / encolure = {{neckline_style}} (col roulé, col montant, col V, col rond, boutonné…)
                    - Logo ou détail distinctif = {{special_logo}} (ex : ruban rose pour la lutte contre le cancer du sein)
                    - Capuche = {{has_hood}} (true si la capuche est visible)
                    - Notes style/techniques = {{feature_notes}} / {{technical_features}} (Polartec, Omni-Heat, renforts, poches…)
                    - Composition = {{cotton_pct}}, {{wool_pct}}, {{cashmere_pct}}, {{polyester_pct}}, {{polyamide_pct}}, {{viscose_pct}}, {{elastane_pct}}, {{nylon_pct}}, {{acrylic_pct}}
                    - Made in = {{made_in}}
                    - Défauts = {{defects}} + {{defect_tags}}
                    - Visibilité des étiquettes = {{size_label_visible}}, {{fabric_label_visible}}, {{fabric_label_cut}}, {{non_size_labels_visible}}
                    - SKU = {{sku}} (PTNF + chiffres pour The North Face, PC + chiffres pour Columbia, n ∈ [1;999], sans tiret)

                    Règles :
                    - Le bloc Commentaire est prioritaire : si l'utilisateur indique taille, coupe, matière ou défaut, applique ces informations avant toute déduction des photos pour remplir les champs, calculer l'estimation et rédiger l'annonce.
                    - Les mensurations à plat sont obligatoires dès qu’une photo claire les affiche.
                    - Dans le titre, combine un maximum de détails : {{zip_style}} (full zip / 1/4 zip / boutons…) + {{neckline_style}} (col roulé / col montant / col V / col rond) et signale toute information {{special_logo}} visible (ex : ruban rose).
                    - Sauf commentaire explicite dans la boîte Commentaire mentionnant une autre fibre, considère les polaires comme 100% polyester quand l’étiquette n’est pas lisible : renseigne {{polyester_pct}} = "100" et laisse les autres champs matière vides.
                    - Ne mentionne la matière dans le titre que pour les fibres intéressantes (coton, laine, cachemire, soie) et jamais avec un pourcentage.
                    - Le SKU doit respecter exactement le format PTNF + chiffres ou PC + chiffres (pas de tiret) et ne jamais être inventé ; renvoie la chaîne vide si l’information manque.
                    - Signale toute étiquette coupée via {{fabric_label_cut}} et rappelle si les étiquettes taille/composition sont absentes.
                    - Ajoute un hashtag dédié aux tailles : #durin31f{{fr_size}} pour un modèle femme, #durin31h{{fr_size}} pour un modèle homme (majuscule), ou adapte pour une version mixte.

                    Utilise ce format :
                    TITRE
                    Polaire {{brand}} {{gender}} taille {{fr_size}} {{zip_style}} {{neckline_style}} {{special_logo}} {{color_main}} - {{sku}}

                    DESCRIPTION + HASHTAG
                    Polaire {{brand}} pour {{gender}}.
                    Taille {{fr_size}} (ou estimation via mesures). {{zip_style}} {{feature_notes}}.
                    {{technical_features}}
                    Composition : {{cotton_pct}}% coton{{#if wool_pct}}, laine{{/if}}{{#if cashmere_pct}}, cachemire{{/if}}{{#if polyester_pct}}, {{polyester_pct}}% polyester{{/if}}… (respecte exactement l’étiquette ou applique la règle 100% polyester par défaut).
                    Très bon état {{defects}} (voir photos). Mentionne les étiquettes coupées quand c’est le cas.
                    📏 Mesures détaillées visibles en photo.
                    📦 Envoi rapide et soigné

                    ✨ Retrouvez toutes mes polaires {{brand}} ici 👉 #durin31{{brand_short_code}}{{fr_size}}

                    👀 Filtrez toutes mes pièces {{gender}} taille {{fr_size}} (polaire, pull, jacket…) 👉 #durin31f{{fr_size}} ou #durin31h{{fr_size}} selon le genre

                    💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !

                    #thenorthface ou #columbia selon la marque + hashtags outdoor (max 10, inclure le hashtag taille #durin31f{{fr_size}} / #durin31h{{fr_size}}).
                    """
                ).strip(),
                render_callback=render_template_polaire_outdoor,
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
