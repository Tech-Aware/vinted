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
