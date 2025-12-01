from __future__ import annotations

import re
import unicodedata
from typing import List, Optional


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
