from __future__ import annotations

"""
Heuristic helpers for inferring the best listing template.

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

from typing import Iterable, Sequence


class TemplateClassificationError(RuntimeError):
    """Raised when the template classifier cannot confidently pick a template."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


_LEVIS_KEYWORDS = (
    "levis",
    "levi's",
    "levi’s",
    "501",
    "505",
    "jean",
    "denim",
    "rivets",
)

_TOMMY_KEYWORDS = (
    "tommy",
    "hilfiger",
    "pull",
    "sweater",
    "mariniere",
    "tricot",
    "knit",
)

_LEVIS_IMAGE_TOKENS = (
    "levis",
    "denim",
    "redtab",
    "rivets",
)

_TOMMY_IMAGE_TOKENS = (
    "tommy",
    "hilfiger",
    "flag",
    "knit",
)


def _score_text(content: str, keywords: Sequence[str]) -> int:
    normalized = content.casefold()
    return sum(1 for keyword in keywords if keyword and keyword in normalized)


def _score_images(encoded_images: Iterable[str], tokens: Sequence[str]) -> int:
    score = 0
    for image in encoded_images:
        if not image:
            continue
        score += _score_text(image, tokens)
    return score


def infer_template(encoded_images: Sequence[str], user_comment: str) -> str:
    """Return the template name based on encoded images and the user comment."""

    comment = (user_comment or "").strip()
    levis_score = _score_text(comment, _LEVIS_KEYWORDS)
    tommy_score = _score_text(comment, _TOMMY_KEYWORDS)

    levis_score += _score_images(encoded_images, _LEVIS_IMAGE_TOKENS)
    tommy_score += _score_images(encoded_images, _TOMMY_IMAGE_TOKENS)

    if levis_score > tommy_score:
        return "template-jean-levis-femme"
    if tommy_score > levis_score:
        return "template-pull-tommy-femme"

    raise TemplateClassificationError(
        "Classification automatique incertaine : sélectionnez manuellement un modèle."
    )

