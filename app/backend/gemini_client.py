"""Client léger pour l'API Gemini, compatible avec les prompts internes."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import List, Sequence

from app.logger import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - dépendance optionnelle
    import google.generativeai as genai
except ImportError:  # pragma: no cover - dépendance optionnelle
    genai = None  # type: ignore


_DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$")


def _data_url_to_inline_data(url: str) -> dict:
    match = _DATA_URL_RE.match(url)
    if not match:
        raise ValueError("URL d'image invalide pour Gemini")

    mime_type = match.group("mime")
    payload = base64.b64decode(match.group("data"))
    return {"inline_data": {"mime_type": mime_type, "data": payload}}


def _messages_to_parts(messages: Sequence[dict]) -> List[object]:
    parts: List[object] = []
    for message in messages:
        for content in message.get("content", []):
            content_type = content.get("type") if isinstance(content, dict) else None
            if isinstance(content, str):
                parts.append(content)
                continue
            if content_type in {"input_text", "text"}:
                text = content.get("text") or ""
                if text:
                    parts.append(text)
            elif content_type in {"input_image", "image_url"}:
                image_url = content.get("image_url") or ""
                try:
                    parts.append(_data_url_to_inline_data(image_url))
                except ValueError:
                    logger.warning("Image ignorée (format non supporté par Gemini)")
    return parts


@dataclass
class GeminiClient:
    """Enveloppe minimaliste autour du SDK Gemini."""

    model: str
    api_key: str

    def _ensure_client(self) -> None:
        if genai is None:
            raise RuntimeError(
                "Le package 'google-generativeai' est requis pour utiliser Gemini."
            )
        if not self.api_key:
            raise RuntimeError("Clé API Gemini manquante")
        genai.configure(api_key=self.api_key)

    def generate(self, messages: Sequence[dict], *, max_tokens: int, temperature: float) -> str:
        """Déclenche une génération Gemini en convertissant les messages internes."""

        self._ensure_client()
        parts = _messages_to_parts(messages)
        if not parts:
            raise ValueError("Prompt vide pour Gemini")

        model = genai.GenerativeModel(self.model)
        response = model.generate_content(
            parts,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        return self._extract_text(response)

    def _extract_text(self, response: object) -> str:
        """Récupère le texte même lorsque `response.text` échoue (blocage sécurité)."""

        # Le quick accessor `response.text` déclenche une ValueError si la réponse est
        # vide ou bloquée par les filtres de sécurité. On l'essaye prudemment puis on
        # retombe sur les candidats.
        try:
            text = getattr(response, "text")  # property potentiellement levante
            if isinstance(text, str) and text:
                return text
        except Exception as exc:  # pragma: no cover - dépendance externe
            logger.warning("Texte Gemini indisponible via response.text : %s", exc)

        candidates = getattr(response, "candidates", None)
        if isinstance(candidates, Sequence):
            texts: List[str] = []
            blocked = False
            for candidate in candidates:
                safety = getattr(candidate, "safety_ratings", None)
                if safety and any(getattr(rating, "blocked", False) for rating in safety):
                    blocked = True
                content = getattr(candidate, "content", None)
                parts = getattr(content, "parts", None) if content else None
                if not parts:
                    parts = getattr(candidate, "parts", None)
                if isinstance(parts, Sequence):
                    for part in parts:
                        text_part = getattr(part, "text", None)
                        if isinstance(text_part, str) and text_part:
                            texts.append(text_part)
            if texts:
                return "".join(texts).strip()
            if blocked:
                raise ValueError(
                    "Réponse Gemini bloquée par les filtres de sécurité (aucun texte)."
                )

        raise ValueError("Réponse Gemini sans contenu textuel exploitable")
