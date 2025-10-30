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


@dataclass
class TopSizeEstimate:
    estimated_size: Optional[str]
    note: Optional[str]
    length_descriptor: Optional[str]


_ELASTANE_NOTE = "Mesure FR étendue par la présence d'élasthane dans la composition"
_WAIST_MEASUREMENT_NOTE = (
    "Taille estimée à partir du tour de taille mesuré visuellement sur les photos"
)
_CM_PER_INCH = 2.54

_SIZE_CHART_BUST_CM = (
    (84.0, "FR 34 (XS)"),
    (88.0, "FR 36 (S)"),
    (92.0, "FR 38 (M)"),
    (98.0, "FR 40 (L)"),
    (104.0, "FR 42 (XL)"),
    (112.0, "FR 44 (XXL)"),
)

_MIN_REASONABLE_BUST_CM = 70.0
_MAX_REASONABLE_BUST_CM = 130.0


def _format_measurement(value: float) -> str:
    return f"~{int(round(value))} cm"


def _describe_top_length(length_measurement_cm: Optional[float]) -> Optional[str]:
    if length_measurement_cm is None or length_measurement_cm <= 0:
        return None

    if length_measurement_cm < 52:
        return (
            f"Coupe courte ({_format_measurement(length_measurement_cm)} de l'épaule à l'ourlet)."
        )
    if length_measurement_cm <= 62:
        return (
            f"Longueur standard ({_format_measurement(length_measurement_cm)} de l'épaule à l'ourlet)."
        )
    return (
        f"Coupe longue ({_format_measurement(length_measurement_cm)} de l'épaule à l'ourlet)."
    )


def estimate_fr_top_size(
    bust_flat_measurement_cm: Optional[float], *, length_measurement_cm: Optional[float] = None
) -> TopSizeEstimate:
    """Estimate a FR top size from a flat bust measurement.

    The function doubles the flat bust measurement to approximate the chest circumference
    unless the input already looks like a full tour (within the realistic min/max range).
    The inferred circumference is mapped to a FR size bracket ranging from XS to XXL. A
    descriptive note explicitly reminds whether the computation relies on the flat width
    multiplied by two or on a provided full measurement. When the measurement falls outside
    of reasonable human ranges, no size is returned and the note highlights the incoherence.
    A shoulder-to-hem length, when available, is converted to a qualitative descriptor
    (court/standard/long).
    """

    length_descriptor = _describe_top_length(length_measurement_cm)

    if bust_flat_measurement_cm is None or bust_flat_measurement_cm <= 0:
        return TopSizeEstimate(estimated_size=None, note=None, length_descriptor=length_descriptor)

    measurement_is_circumference = (
        _MIN_REASONABLE_BUST_CM
        <= bust_flat_measurement_cm
        <= _MAX_REASONABLE_BUST_CM
    )

    if measurement_is_circumference:
        chest_circumference_cm = bust_flat_measurement_cm
    else:
        chest_circumference_cm = bust_flat_measurement_cm * 2
    rounded_circumference = int(round(chest_circumference_cm))

    if chest_circumference_cm < _MIN_REASONABLE_BUST_CM:
        note = (
            f"Mesure de poitrine trop faible pour une taille adulte (~{rounded_circumference} cm)."
        )
        return TopSizeEstimate(estimated_size=None, note=note, length_descriptor=length_descriptor)

    if chest_circumference_cm > _MAX_REASONABLE_BUST_CM:
        note = (
            f"Mesure de poitrine hors plage réaliste (~{rounded_circumference} cm)."
        )
        return TopSizeEstimate(estimated_size=None, note=note, length_descriptor=length_descriptor)

    estimated_size: Optional[str] = None
    for upper_bound, label in _SIZE_CHART_BUST_CM:
        if chest_circumference_cm <= upper_bound:
            estimated_size = label
            break

    if estimated_size is None:
        note = f"Mesure de poitrine hors grille (~{rounded_circumference} cm)."
        return TopSizeEstimate(estimated_size=None, note=note, length_descriptor=length_descriptor)

    if measurement_is_circumference:
        note = f"Taille estimée depuis un tour de poitrine ~{rounded_circumference} cm."
    else:
        note = (
            f"Taille estimée depuis un tour de poitrine ~{rounded_circumference} cm "
            "(largeur à plat x2)."
        )
    return TopSizeEstimate(
        estimated_size=estimated_size, note=note, length_descriptor=length_descriptor
    )


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


def fr_size_from_waist_measurement(
    waist_measurement_cm: Optional[float], *, ensure_even: bool = True
) -> Optional[str]:
    """Convert a waist measurement in centimeters to the closest FR size."""

    if waist_measurement_cm is None:
        return None
    if waist_measurement_cm <= 0:
        return None

    us_equivalent = waist_measurement_cm / _CM_PER_INCH
    # Round to the nearest integer to match standard W measurements.
    us_size = int(round(us_equivalent))
    if us_size <= 0:
        return None

    fr_value = us_size + 10
    if ensure_even and fr_value % 2:
        fr_value += 1
    return str(fr_value)


def normalize_sizes(
    us_w: Optional[str],
    fr_size: Optional[str],
    has_elastane: bool,
    *,
    ensure_even_fr: bool = False,
    waist_measurement_cm: Optional[float] = None,
) -> NormalizedSizes:
    """Apply the business rule converting US W to FR sizes.

    - When both values exist, compute the difference ``delta = FR - US``. If ``delta``
      is outside the expected range [8, 12], only keep the FR value. When the delta is
      greater than 12 and elastane is present, add a dedicated note.
    - Otherwise fall back to computing ``FR = US + 10`` when a US size exists.
    - When ``ensure_even_fr`` is ``True``, an FR size derived from the US measurement
      is rounded up to the next even number.
    - When both FR and US labels are missing, rely on the waist measurement in
      centimeters to infer a normalized FR size.
    """

    us_value = _extract_int(us_w)
    fr_value = _extract_int(fr_size)

    def _from_us(value: int) -> int:
        computed = value + 10
        if ensure_even_fr and computed % 2:
            computed += 1
        return computed

    if us_value is not None and fr_value is not None:
        delta = fr_value - us_value
        if delta > 12 or delta < 8:
            note = _ELASTANE_NOTE if has_elastane and delta > 12 else None
            return NormalizedSizes(fr_size=str(fr_value), us_size=None, note=note)
        computed_fr = _from_us(us_value)
        return NormalizedSizes(fr_size=str(computed_fr), us_size=str(us_value), note=None)

    if us_value is not None:
        computed_fr = _from_us(us_value)
        return NormalizedSizes(fr_size=str(computed_fr), us_size=str(us_value), note=None)

    if fr_value is not None:
        return NormalizedSizes(fr_size=str(fr_value), us_size=None, note=None)

    measurement_fr = fr_size_from_waist_measurement(
        waist_measurement_cm, ensure_even=ensure_even_fr
    )
    if measurement_fr is not None:
        measurement_note = _WAIST_MEASUREMENT_NOTE
        if waist_measurement_cm is not None:
            measurement_note = (
                f"{measurement_note} (~{int(round(waist_measurement_cm))} cm)."
            )
        return NormalizedSizes(
            fr_size=measurement_fr, us_size=None, note=measurement_note
        )

    return NormalizedSizes(fr_size=None, us_size=None, note=None)

