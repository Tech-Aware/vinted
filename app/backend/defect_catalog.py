"""Reference catalog for standardized defect mentions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class DefectSpec:
    """Describe a standardized defect mention."""

    slug: str
    synonyms: Sequence[str]
    description: str


def _build_catalog(specs: Iterable[DefectSpec]) -> Dict[str, DefectSpec]:
    return {spec.slug: spec for spec in specs}


_CATALOG_SPECS: Sequence[DefectSpec] = (
    DefectSpec(
        slug="faded_crotch",
        synonyms=(
            "entrejambe délavé",
            "crotch fade",
            "décoloration entrejambe",
        ),
        description="Entrejambe légèrement délavée, voir photos",
    ),
    DefectSpec(
        slug="stylish_holes",
        synonyms=(
            "trou stylé",
            "effet troué",
            "distressed hole",
        ),
        description="Effets troués pour un style plus affirmé",
    ),
)


DEFECT_CATALOG: Dict[str, DefectSpec] = _build_catalog(_CATALOG_SPECS)
"""Mapping of defect slug to their specification."""


def get_defect_descriptions(slugs: Sequence[str]) -> List[str]:
    """Return the standardized descriptions for the provided slugs.

    Unknown slugs are ignored to keep rendering resilient to outdated
    instructions while still allowing validation upstream.
    """

    seen: set[str] = set()
    descriptions: List[str] = []
    for slug in slugs:
        if slug in seen:
            continue
        seen.add(slug)
        spec = DEFECT_CATALOG.get(slug)
        if spec and spec.description:
            descriptions.append(spec.description)
    return descriptions


def known_defect_slugs() -> Sequence[str]:
    """Expose the list of known defect slugs."""

    return tuple(DEFECT_CATALOG.keys())
