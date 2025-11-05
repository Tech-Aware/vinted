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
from typing import Optional, Tuple


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


def _compute_fr_from_waist_measurement(
    measurement_cm: float, *, ensure_even_fr: bool
) -> Optional[Tuple[int, int, float]]:
    """Convert a raw waist measurement to FR/US size equivalents."""

    if measurement_cm <= 0:
        return None

    circumference_cm = measurement_cm * 2 if measurement_cm < 60 else measurement_cm
    if circumference_cm <= 0:
        return None

    waist_inch = circumference_cm / _CM_PER_INCH
    if waist_inch <= 0:
        return None

    us_numeric = int(round(waist_inch))
    if us_numeric <= 0:
        return None

    fr_float = waist_inch + 10
    fr_numeric = int(round(fr_float))

    if ensure_even_fr and fr_numeric % 2:
        lower_even = fr_numeric - 1
        upper_even = fr_numeric + 1
        candidates: list[Tuple[float, int]] = []
        if lower_even > 0:
            candidates.append((abs(fr_float - lower_even), lower_even))
        candidates.append((abs(fr_float - upper_even), upper_even))
        candidates.sort(key=lambda item: (item[0], item[1]))
        fr_numeric = candidates[0][1]

    if fr_numeric <= 0:
        return None

    return fr_numeric, us_numeric, circumference_cm

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
    """Convert a waist measurement in centimeters to a FR size value."""

    if waist_measurement_cm is None:
        return None

    try:
        numeric_value = float(waist_measurement_cm)
    except (TypeError, ValueError):
        return None

    estimate = _compute_fr_from_waist_measurement(
        numeric_value, ensure_even_fr=ensure_even
    )
    if estimate is None:
        return None

    fr_numeric, _us_numeric, _circumference = estimate
    return str(fr_numeric)


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

    measurement_estimate: Optional[Tuple[int, int, float]] = None
    if measurement_numeric is not None:
        measurement_estimate = _compute_fr_from_waist_measurement(
            measurement_numeric, ensure_even_fr=ensure_even_fr
        )

    measurement_value: Optional[int] = None
    measurement_note: Optional[str] = None
    measurement_sizes: Optional[NormalizedSizes] = None
    if measurement_estimate is not None:
        measurement_fr_numeric, _measurement_us_numeric, measurement_circumference = (
            measurement_estimate
        )
        measurement_value = measurement_fr_numeric
        measurement_note = _WAIST_MEASUREMENT_NOTE
        measurement_note = (
            f"{measurement_note} (~{int(round(measurement_circumference))} cm)."
        )
        measurement_sizes = NormalizedSizes(
            fr_size=str(measurement_fr_numeric), us_size=None, note=measurement_note
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

