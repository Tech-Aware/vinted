"""Client léger pour l'API Gemini, compatible avec les prompts internes."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import List, Sequence

from app.logger import get_logger

logger = get_logger(__name__)


def _ensure_importlib_compatibility() -> None:
    """Ajoute packages_distributions à importlib.metadata si absent (Python 3.9)."""

    try:  # pragma: no cover - dépendance standard
        import importlib.metadata as stdlib_metadata
    except Exception:
        return

    if hasattr(stdlib_metadata, "packages_distributions"):
        return

    # Tentative de récupération depuis le backport importlib_metadata si disponible.
    try:  # pragma: no cover - dépendance optionnelle
        import importlib_metadata as backport_metadata

        stdlib_metadata.packages_distributions = backport_metadata.packages_distributions  # type: ignore[attr-defined]
        logger.info(
            "Compatibilité importlib: packages_distributions injecté depuis importlib_metadata"
        )
        return
    except Exception:
        pass

    # Dernier recours : stub minimal pour éviter l'AttributeError au chargement de google-generativeai.
    def _fallback_packages_distributions():
        return {}

    stdlib_metadata.packages_distributions = _fallback_packages_distributions  # type: ignore[attr-defined]
    logger.warning(
        "Compatibilité importlib: utilisation d'un stub packages_distributions; "
        "mettez à jour Python ou installez importlib_metadata pour un support complet"
    )


_ensure_importlib_compatibility()


class GeminiResponseError(RuntimeError):
    """Erreur de contenu Gemini destinée à l'affichage utilisateur."""

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
                # Force une sortie textuelle exploitable (sinon certaines variantes
                # peuvent retourner des structures sans texte).
                "response_mime_type": "text/plain",
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
            blocked_reasons: List[str] = []
            finish_reasons: List[str] = []

            for candidate in candidates:
                safety = getattr(candidate, "safety_ratings", None)
                if safety:
                    for rating in safety:
                        category = getattr(rating, "category", None)
                        if getattr(rating, "blocked", False):
                            blocked = True
                            if isinstance(category, str) and category:
                                blocked_reasons.append(category)
                        elif isinstance(category, str) and category:
                            # Même non bloqué, on conserve les catégories pour le diagnostic.
                            blocked_reasons.append(category)

                finish_reason = getattr(candidate, "finish_reason", None)
                if isinstance(finish_reason, str) and finish_reason:
                    finish_reasons.append(finish_reason)

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

            reason_chunks: List[str] = []
            if blocked_reasons:
                reason_chunks.append(
                    "raisons de sécurité : " + ", ".join(sorted(set(blocked_reasons)))
                )
            if finish_reasons:
                reason_chunks.append(
                    "codes de fin : " + ", ".join(sorted(set(finish_reasons)))
                )

            if blocked:
                detail = f" ({'; '.join(reason_chunks)})" if reason_chunks else ""
                raise GeminiResponseError(
                    "Réponse Gemini bloquée : aucun texte renvoyé" +
                    f"{detail}. Vérifiez le contenu (images/texte) et réessayez."
                )

            if reason_chunks:
                raise GeminiResponseError(
                    "Réponse Gemini sans contenu textuel exploitable : "
                    + "; ".join(reason_chunks)
                    + ". Vérifiez le message d'entrée et réessayez."
                )

        raise GeminiResponseError(
            "Réponse Gemini sans contenu textuel exploitable : la sortie est vide ou a "
            "été filtrée par la sécurité. Vérifiez le message d'entrée et réessayez."
        )
