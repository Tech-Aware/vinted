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

"""Utilities dedicated to post-processing natural language fields."""

from typing import Optional, Tuple

import re
import unicodedata


_FIT_NORMALIZATION = {
    "bootcut": ("Bootcut/Évasé", "bootcut/évasé"),
    "straight": ("Straight/Droit", "straight/droit"),
    "slim": ("Skinny", "skinny"),
}

_COLOR_TRANSLATIONS = {
    "black": "noir",
    "blue": "bleu",
    "dark blue": "bleu foncé",
    "light blue": "bleu clair",
    "navy": "bleu marine",
    "white": "blanc",
    "red": "rouge",
    "burgundy": "bordeaux",
    "pink": "rose",
    "purple": "violet",
    "green": "vert",
    "dark green": "vert foncé",
    "light green": "vert clair",
    "yellow": "jaune",
    "orange": "orange",
    "brown": "marron",
    "beige": "beige",
    "grey": "gris",
    "gray": "gris",
    "light grey": "gris clair",
    "light gray": "gris clair",
    "dark grey": "gris foncé",
    "dark gray": "gris foncé",
}

_COLOR_COMPOUND_SEPARATOR_PATTERN = re.compile(
    r"(\s*(?:/|,|&|\+)\s*|\s+\bet\b\s+|\s+\band\b\s+)"
)

_FIT_ALIASES = {
    "bootcut": "bootcut",
    "evase": "bootcut",
    "bootcut/evase": "bootcut",
    "straight": "straight",
    "droit": "straight",
    "straight/droit": "straight",
    "slim": "slim",
    "skinny": "slim",
    "skinny/slim": "slim",
}

_MODEL_CODE_PATTERN = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")


def _strip_accents(value: str) -> str:
    """Return a lowercase string without diacritics."""

    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _normalize_fit_lookup(raw_value: str) -> str:
    """Normalize raw fit descriptions to the lookup keys used internally."""

    cleaned = raw_value.strip().lower()
    if not cleaned:
        return ""

    cleaned = cleaned.replace("-", "/")
    cleaned = cleaned.replace("(", "").replace(")", "")
    cleaned = re.sub(r"\s*/\s*", "/", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = _strip_accents(cleaned)

    alias = _FIT_ALIASES.get(cleaned)
    if alias:
        return alias

    for token in cleaned.replace("/", " ").split():
        alias = _FIT_ALIASES.get(token)
        if alias:
            return alias

    return cleaned

def _translate_single_color_term(term: str) -> str:
    """Translate an individual color descriptor when possible."""

    fragment = term.strip()
    if not fragment:
        return ""

    normalized = _strip_accents(fragment.lower())
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    translation = _COLOR_TRANSLATIONS.get(normalized)
    if translation:
        return translation

    return fragment.lower()


def translate_color_to_french(color: Optional[str]) -> Optional[str]:
    """Translate a color name provided in English into French when known."""

    if color is None:
        return None

    cleaned = color.strip()
    if not cleaned:
        return ""

    normalized = _strip_accents(cleaned.lower())
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    translation = _COLOR_TRANSLATIONS.get(normalized)
    if translation:
        return translation

    parts = _COLOR_COMPOUND_SEPARATOR_PATTERN.split(cleaned)
    if len(parts) > 1:
        translated_parts = []
        for part in parts:
            if not part:
                continue
            if _COLOR_COMPOUND_SEPARATOR_PATTERN.fullmatch(part):
                lowered = part.lower()
                if "/" in part:
                    translated_parts.append(" / ")
                elif "," in part:
                    translated_parts.append(", ")
                elif any(symbol in part for symbol in {"&", "+"}):
                    translated_parts.append(" et ")
                elif " et " in lowered:
                    translated_parts.append(" et ")
                elif " and " in lowered:
                    translated_parts.append(" et ")
            else:
                translated_fragment = _translate_single_color_term(part)
                if translated_fragment:
                    translated_parts.append(translated_fragment)
        if translated_parts:
            combined = "".join(translated_parts)
            combined = re.sub(r"\s{2,}", " ", combined).strip()
            if combined:
                return combined

    return cleaned.lower()


def normalize_fit_terms(fit_leg: Optional[str]) -> Tuple[str, str, str]:
    """Return the preferred wording for the title, description and hashtag.

    The first element corresponds to the bilingual wording that must appear in the
    title, the second one contains the lowercase variant used in the description,
    and the third corresponds to a lowercase slug suitable for hashtags.
    """

    if not fit_leg:
        return "", "", ""

    raw = fit_leg.strip()
    lookup = _normalize_fit_lookup(raw)
    normalized = _FIT_NORMALIZATION.get(lookup)
    if normalized:
        title_term, description_term = normalized
        hashtag_term = lookup.replace(" ", "")
    else:
        title_term = raw
        description_term = raw
        hashtag_term = _normalize_fit_lookup(raw).replace(" ", "")
    return title_term, description_term, hashtag_term


def normalize_model_code(model: Optional[str]) -> Optional[str]:
    """Extract the Levi's model code and optionally append the Premium suffix."""

    if not model:
        return model

    cleaned = model.strip()
    if not cleaned:
        return model

    match = _MODEL_CODE_PATTERN.search(cleaned)
    if not match:
        return model

    code = match.group(1)
    has_premium = "premium" in cleaned.lower()
    return f"{code} Premium" if has_premium else code

