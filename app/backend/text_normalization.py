"""Utilities dedicated to post-processing natural language fields."""
from __future__ import annotations

from typing import Tuple


_FIT_NORMALIZATION = {
    "bootcut": ("évasé", "bootcut/évasé"),
    "straight": ("droit", "straight/droit"),
    "slim": ("skinny", "skinny/slim"),
}


def normalize_fit_terms(fit_leg: str | None) -> Tuple[str, str, str]:
    """Return the preferred wording for the title, description and hashtag.

    The first element corresponds to the French-only variant that must appear in the
    title, the second one contains both the English and French wording for the
    description, and the third corresponds to a lowercase slug suitable for
    hashtags.
    """

    if not fit_leg:
        return "", "", ""

    raw = fit_leg.strip()
    lookup = raw.lower()
    normalized = _FIT_NORMALIZATION.get(lookup)
    if normalized:
        title_term, description_term = normalized
    else:
        title_term = raw
        description_term = raw
    hashtag_term = lookup.replace(" ", "")
    return title_term, description_term, hashtag_term

