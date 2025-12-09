"""Client Gemini basé sur le SDK `google-genai`.

Ce module convertit les messages internes en payload compatible avec
`generate_content` (texte + images) et applique une configuration minimaliste
pour obtenir une réponse textuelle exploitable.
"""

from __future__ import annotations

import base64
import importlib
import importlib.metadata
import re
from dataclasses import dataclass
from typing import Any, List, Sequence

from app.logger import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - dépendance externe
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except Exception:  # pragma: no cover - dépendance externe
    genai = None  # type: ignore
    types = None  # type: ignore
    GENAI_AVAILABLE = False


_DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$")


def _coerce_attr(obj: object, name: str):
    """Récupère un attribut ou une clé de dictionnaire sans lever."""

    if isinstance(obj, dict):
        return obj.get(name)
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _patch_importlib_metadata() -> None:
    """Assure la présence de ``packages_distributions`` pour google-generativeai."""

    try:
        importlib.metadata.packages_distributions  # type: ignore[attr-defined]
        return
    except Exception:
        pass

    try:  # pragma: no cover - dépendance externe
        import importlib_metadata

        if hasattr(importlib_metadata, "packages_distributions"):
            importlib.metadata.packages_distributions = (  # type: ignore[attr-defined]
                importlib_metadata.packages_distributions
            )
            logger.info(
                "Compatibilité importlib: packages_distributions injecté depuis importlib_metadata"
            )
    except Exception:
        logger.warning(
            "Impossible d'injecter packages_distributions ; l'import de google-generativeai peut échouer"
        )


def _data_url_to_part(url: str) -> Any:
    """Convertit une data URL base64 en `Part` Gemini ou en inline_data."""

    match = _DATA_URL_RE.match(url)
    if not match:
        raise ValueError("URL d'image invalide pour Gemini")

    mime_type = match.group("mime")
    payload = base64.b64decode(match.group("data"))

    if types is not None:  # pragma: no cover - dépendance externe
        try:
            return types.Part.from_bytes(data=payload, mime_type=mime_type)
        except Exception:
            pass

    b64_payload = base64.b64encode(payload).decode("utf-8")
    return {"inline_data": {"mime_type": mime_type, "data": b64_payload}}


def _messages_to_payload(messages: Sequence[dict]) -> tuple[List[Any], str | None]:
    """Convertit les messages internes en liste de parties Gemini.

    Le SDK accepte une liste de parties (texte ou images) et, en option, une
    instruction système. On concatène les textes système en une seule chaîne
    pour alimenter `system_instruction`.
    """

    contents: List[Any] = []
    system_texts: List[str] = []

    for message in messages:
        role = message.get("role") or "user"
        for content in message.get("content", []):
            if isinstance(content, str):
                text = content.strip()
                if not text:
                    continue
                (system_texts if role == "system" else contents).append(text)
                continue

            if not isinstance(content, dict):
                continue

            content_type = content.get("type")
            if content_type in {"input_text", "text"}:
                text = (content.get("text") or "").strip()
                if text:
                    (system_texts if role == "system" else contents).append(text)
            elif content_type in {"input_image", "image_url"}:
                image_url = content.get("image_url") or ""
                try:
                    part = _data_url_to_part(image_url)
                    contents.append(part)
                except ValueError:
                    logger.warning("Image ignorée (format non supporté par Gemini)")

    system_instruction = "\n\n".join(system_texts) if system_texts else None
    return contents, system_instruction


class GeminiResponseError(RuntimeError):
    """Erreur de contenu Gemini destinée à l'affichage utilisateur."""


@dataclass
class GeminiClient:
    """Enveloppe minimaliste autour du client Gemini."""

    model: str
    api_key: str
    _client: Any | None = None
    _backend: str | None = None  # "genai" ou "generativeai"

    def _ensure_client(self):
        # Import paresseux pour permettre l'installation après le démarrage.
        global genai, types  # pragma: no cover - dépendance externe
        if not self.api_key:
            raise RuntimeError("Clé API Gemini manquante")

        if self._client is not None:
            return self._client

        _patch_importlib_metadata()

        # Tentative d'utilisation du SDK google-genai (recommandé)
        if genai is None or types is None:
            try:
                from google import genai as genai_module  # type: ignore
                from google.genai import types as genai_types  # type: ignore

                genai = genai_module
                types = genai_types
                self._backend = "genai"
                self._client = genai.Client(api_key=self.api_key)
                return self._client
            except Exception as exc_genai:  # pragma: no cover - dépendance externe
                logger.warning(
                    "Import google-genai impossible, tentative avec google-generativeai : %s",
                    exc_genai,
                )

        if genai is not None and types is not None:
            self._backend = "genai"
            self._client = genai.Client(api_key=self.api_key)
            return self._client

        # Repli sur google-generativeai (compatible Python 3.9)
        try:  # pragma: no cover - dépendance externe
            import google.generativeai as genai_legacy  # type: ignore

            genai_legacy.configure(api_key=self.api_key)
            self._backend = "generativeai"
            self._client = genai_legacy.GenerativeModel(self.model)
            return self._client
        except Exception as exc_legacy:  # pragma: no cover - dépendance externe
            raise GeminiResponseError(
                "Les dépendances Gemini sont manquantes ou incompatibles. "
                "Installez `google-genai` ou `google-generativeai` via "
                "`pip install -r requirements.txt`."
            ) from exc_legacy

    def generate(
        self, messages: Sequence[dict], *, max_tokens: int, temperature: float
    ) -> str:
        """Déclenche une génération Gemini en convertissant les messages internes."""

        client = self._ensure_client()
        contents, system_instruction = _messages_to_payload(messages)
        if not contents:
            raise ValueError("Prompt vide pour Gemini")

        if self._backend == "genai":
            config_kwargs = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "response_mime_type": "application/json",
            }
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction

            config = types.GenerateContentConfig(**config_kwargs)
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return self._extract_text(response)

        # Repli google-generativeai (API proche mais sans config objet dédié)
        # Ce SDK attend une liste de contenus structurés avec un rôle et des parts.
        combined_parts: List[Any] = []

        if system_instruction:
            combined_parts.append(system_instruction)
        combined_parts.extend(contents)

        safe_parts: List[Any] = []
        for part in combined_parts:
            if hasattr(part, "to_dict"):
                safe_parts.append(part.to_dict())
            elif isinstance(part, dict):
                safe_parts.append(part)
            else:
                safe_parts.append(part)

        payload = [{"role": "user", "parts": safe_parts}]

        response = client.generate_content(
            payload,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "response_mime_type": "application/json",
            },
        )
        return self._extract_text(response)

    def _extract_text(self, response: object) -> str:
        """Récupère le texte d'une réponse Gemini en évitant les ValueError."""

        try:  # pragma: no cover - dépendance externe
            text = getattr(response, "text", None)
            if isinstance(text, str) and text.strip():
                return text.strip()
        except Exception as exc:
            logger.warning("Texte Gemini indisponible via response.text : %s", exc)

        output_text = _coerce_attr(response, "output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        candidates = _coerce_attr(response, "candidates")
        texts: List[str] = []
        blocked_reasons: List[str] = []
        finish_reasons: List[str] = []

        if isinstance(candidates, Sequence):
            for candidate in candidates:
                finish_reason = _coerce_attr(candidate, "finish_reason")
                if isinstance(finish_reason, str) and finish_reason:
                    finish_reasons.append(finish_reason)

                safety = _coerce_attr(candidate, "safety_ratings")
                if isinstance(safety, Sequence):
                    for rating in safety:
                        category = _coerce_attr(rating, "category")
                        blocked = bool(_coerce_attr(rating, "blocked"))
                        if blocked and isinstance(category, str):
                            blocked_reasons.append(category)

                content = _coerce_attr(candidate, "content")
                parts = _coerce_attr(content, "parts") if content else None
                if not parts:
                    parts = _coerce_attr(candidate, "parts")
                if isinstance(parts, Sequence):
                    for part in parts:
                        text_part = _coerce_attr(part, "text")
                        if isinstance(text_part, str) and text_part:
                            texts.append(text_part)
                        elif isinstance(part, dict):
                            raw_text = part.get("text")
                            if isinstance(raw_text, str) and raw_text:
                                texts.append(raw_text)

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

        raise GeminiResponseError(
            "Réponse Gemini sans contenu textuel exploitable"
            + (" ; " + "; ".join(reason_chunks) if reason_chunks else "")
            + ". Vérifiez le message d'entrée et réessayez."
        )
