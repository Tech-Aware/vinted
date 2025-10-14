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

"""Utility helpers for preparing images for the OpenAI API."""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Iterable, List

from app.logger import get_logger


logger = get_logger(__name__)


def encode_images_to_base64(paths: Iterable[Path]) -> List[str]:
    """Encode image files and return data URLs compatible with the OpenAI API."""

    logger.step("Encodage des images en base64")
    encoded: List[str] = []
    for path in paths:
        file_path = Path(path)
        try:
            with file_path.open("rb") as fh:
                encoded_data = base64.b64encode(fh.read()).decode("utf-8")
        except OSError as exc:
            logger.error("Lecture impossible pour %s", path, exc_info=exc)
            continue

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/jpeg"

        data_url = f"data:{mime_type};base64,{encoded_data}"
        encoded.append(data_url)
        logger.success("Image encodée: %s", path)

    logger.info("%d image(s) encodée(s)", len(encoded))
    return encoded
