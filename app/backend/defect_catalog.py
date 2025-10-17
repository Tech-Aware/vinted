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

"""Reference catalog for standardized defect mentions."""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set


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
        description="Effets troués pour plus style, voir photos",
    ),
    DefectSpec(
            slug="ripped",
            synonyms=(
                "Déchiré",
                "effet déchiré",
                "Slightly ripped",
            ),
            description="Effets déchiré pour un style plus affirmé, voir photos",
        ),
)


DEFECT_CATALOG: Dict[str, DefectSpec] = _build_catalog(_CATALOG_SPECS)
"""Mapping of defect slug to their specification."""


def get_defect_descriptions(slugs: Sequence[str]) -> List[str]:
    """Return the standardized descriptions for the provided slugs.

    Unknown slugs are ignored to keep rendering resilient to outdated
    instructions while still allowing validation upstream.
    """

    seen: Set[str] = set()
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
