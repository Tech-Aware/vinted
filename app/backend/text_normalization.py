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
    "black": "Noir",
    "blue": "Bleu",
    "dark blue": "Bleu foncé",
    "light blue": "Bleu clair",
    "navy": "Bleu marine",
    "white": "Blanc",
    "red": "Rouge",
    "burgundy": "Bordeaux",
    "pink": "Rose",
    "purple": "Violet",
    "green": "Vert",
    "dark green": "Vert foncé",
    "light green": "Vert clair",
    "yellow": "Jaune",
    "orange": "Orange",
    "brown": "Marron",
    "beige": "Beige",
    "grey": "Gris",
    "gray": "Gris",
    "light grey": "Gris clair",
    "light gray": "Gris clair",
    "dark grey": "Gris foncé",
    "dark gray": "Gris foncé",
}

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

    return cleaned


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

