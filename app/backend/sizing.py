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

_WAIST_MEASUREMENT_OVERRIDE_THRESHOLD_CM = 4

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

    return f"Longueur épaule-ourlet {_format_measurement(length_measurement_cm)}."


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
    """Round a waist measurement (cm) to a FR size value.

    The measurement is rounded to the nearest integer centimeter. When ``ensure_even``
    is ``True`` and the rounded value is odd, the next even number is returned.
    """

    if waist_measurement_cm is None:
        return None
    if waist_measurement_cm <= 0:
        return None

    rounded_value = int(round(waist_measurement_cm))
    if rounded_value <= 0:
        return None

    if ensure_even and rounded_value % 2:
        rounded_value += 1
    return str(rounded_value)


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
    - Whenever a waist measurement is provided, compute the corresponding FR size and
      compare it to the labeled FR value (if any) and to the FR size derived from the
      US size. If the measurement differs from either label by at least
      ``_WAIST_MEASUREMENT_OVERRIDE_THRESHOLD_CM``, prefer the measurement: return only
      the measurement-based FR size and keep the measurement note.
    - When both FR and US labels are missing, rely on the waist measurement in
      centimeters to infer a normalized FR size.
    """

    us_value = _extract_int(us_w)
    fr_value = _extract_int(fr_size)

    measurement_numeric: Optional[float]
    if waist_measurement_cm is None:
        measurement_numeric = None
    else:
        try:
            measurement_numeric = float(waist_measurement_cm)
        except (TypeError, ValueError):
            measurement_numeric = None

    if measurement_numeric is not None and measurement_numeric <= 0:
        measurement_numeric = None

    measurement_value: Optional[int] = None
    if measurement_numeric is not None:
        measurement_value = int(round(measurement_numeric))

    measurement_fr = fr_size_from_waist_measurement(
        measurement_numeric, ensure_even=ensure_even_fr
    )
    measurement_note: Optional[str] = None
    measurement_sizes: Optional[NormalizedSizes] = None
    if measurement_fr is not None:
        measurement_note = _WAIST_MEASUREMENT_NOTE
        if measurement_numeric is not None:
            measurement_note = (
                f"{measurement_note} (~{int(round(measurement_numeric))} cm)."
            )
        measurement_sizes = NormalizedSizes(
            fr_size=measurement_fr, us_size=None, note=measurement_note
        )

    def _adjust_even(value: int) -> int:
        if not ensure_even_fr or value % 2 == 0:
            return value
        if measurement_value is not None:
            delta = measurement_value - value
            if abs(delta) <= _WAIST_MEASUREMENT_OVERRIDE_THRESHOLD_CM:
                if delta < 0:
                    return max(0, value - 1)
                if delta > 0:
                    return value + 1
                return value + 1
        return value + 1

    computed_fr_from_us: Optional[int] = None
    us_reference_raw: Optional[int] = None
    if us_value is not None:
        us_reference_raw = us_value + 10
        computed_fr_from_us = _adjust_even(us_reference_raw)

    if (
        measurement_sizes is not None
        and measurement_value is not None
        and (
            (
                fr_value is not None
                and abs(measurement_value - fr_value)
                > _WAIST_MEASUREMENT_OVERRIDE_THRESHOLD_CM
            )
            or (
                us_reference_raw is not None
                and abs(measurement_value - us_reference_raw)
                > _WAIST_MEASUREMENT_OVERRIDE_THRESHOLD_CM
            )
        )
    ):
        return measurement_sizes

    if us_value is not None and fr_value is not None:
        delta = fr_value - us_value
        if delta > 12 or delta < 8:
            note = _ELASTANE_NOTE if has_elastane and delta > 12 else None
            return NormalizedSizes(fr_size=str(fr_value), us_size=None, note=note)
        computed_fr = (
            computed_fr_from_us
            if computed_fr_from_us is not None
            else _adjust_even(us_value + 10)
        )
        return NormalizedSizes(fr_size=str(computed_fr), us_size=str(us_value), note=None)

    if us_value is not None:
        computed_fr = (
            computed_fr_from_us
            if computed_fr_from_us is not None
            else _adjust_even(us_value + 10)
        )
        return NormalizedSizes(fr_size=str(computed_fr), us_size=str(us_value), note=None)

    if fr_value is not None:
        return NormalizedSizes(fr_size=str(fr_value), us_size=None, note=None)

    if measurement_sizes is not None:
        return measurement_sizes

    return NormalizedSizes(fr_size=None, us_size=None, note=None)

