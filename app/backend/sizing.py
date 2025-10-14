"""Utilities handling the size conversion rules between US and FR."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedSizes:
    fr_size: Optional[str]
    us_size: Optional[str]
    note: Optional[str]


_ELASTANE_NOTE = "Mesure FR étendue par la présence d'élasthane dans la composition"


def _extract_int(value: str | None) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"\d+", value)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def normalize_sizes(us_w: str | None, fr_size: str | None, has_elastane: bool) -> NormalizedSizes:
    """Apply the business rule converting US W to FR sizes.

    - When both values exist, compute the difference ``delta = FR - US``. If ``delta``
      is outside the expected range [8, 12], only keep the FR value. When the delta is
      greater than 12 and elastane is present, add a dedicated note.
    - Otherwise fall back to computing ``FR = US + 10`` when a US size exists.
    """

    us_value = _extract_int(us_w)
    fr_value = _extract_int(fr_size)

    if us_value is not None and fr_value is not None:
        delta = fr_value - us_value
        if delta > 12 or delta < 8:
            note = _ELASTANE_NOTE if has_elastane and delta > 12 else None
            return NormalizedSizes(fr_size=str(fr_value), us_size=None, note=note)
        computed_fr = us_value + 10
        return NormalizedSizes(fr_size=str(computed_fr), us_size=str(us_value), note=None)

    if us_value is not None:
        return NormalizedSizes(fr_size=str(us_value + 10), us_size=str(us_value), note=None)

    if fr_value is not None:
        return NormalizedSizes(fr_size=str(fr_value), us_size=None, note=None)

    return NormalizedSizes(fr_size=None, us_size=None, note=None)

