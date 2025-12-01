from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple

from .normalization import _normalize_text_for_comparison

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
