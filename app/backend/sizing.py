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

"""Utilities handling the size conversion rules between US and FR."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedSizes:
    fr_size: Optional[str]
    us_size: Optional[str]
    note: Optional[str]


_ELASTANE_NOTE = "Mesure FR étendue par la présence d'élasthane dans la composition"


def _extract_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"\d+", value)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def normalize_sizes(us_w: Optional[str], fr_size: Optional[str], has_elastane: bool) -> NormalizedSizes:
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

