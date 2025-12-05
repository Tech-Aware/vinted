"""Client léger pour l'API Gemini, compatible avec les prompts internes."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
import inspect
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
    from google.generativeai.types import HarmBlockThreshold, HarmCategory
except ImportError:  # pragma: no cover - dépendance optionnelle
    genai = None  # type: ignore
    HarmCategory = None  # type: ignore
    HarmBlockThreshold = None  # type: ignore


_DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$")


def _data_url_to_inline_data(url: str) -> dict:
    match = _DATA_URL_RE.match(url)
    if not match:
        raise ValueError("URL d'image invalide pour Gemini")

    mime_type = match.group("mime")
    payload = base64.b64decode(match.group("data"))
    return {"inline_data": {"mime_type": mime_type, "data": payload}}


def _messages_to_payload(messages: Sequence[dict]) -> tuple[List[dict], dict | None]:
    """Convertit les messages internes en payload Gemini (contents + system)."""

    contents: List[dict] = []
    system_parts: List[dict] = []

    for message in messages:
        role = message.get("role") or "user"
        parts: List[dict] = []

        for content in message.get("content", []):
            content_type = content.get("type") if isinstance(content, dict) else None

            if isinstance(content, str):
                if content:
                    parts.append({"text": content})
                continue

            if content_type in {"input_text", "text"}:
                text = content.get("text") or ""
                if text:
                    parts.append({"text": text})
            elif content_type in {"input_image", "image_url"}:
                image_url = content.get("image_url") or ""
                try:
                    parts.append(_data_url_to_inline_data(image_url))
                except ValueError:
                    logger.warning("Image ignorée (format non supporté par Gemini)")

        if role == "system":
            system_parts.extend(parts)
            continue

        # Chaque message devient une entrée role + parts si au moins une part est présente
        if parts:
            provider_role = "model" if role == "assistant" else "user"
            contents.append({"role": provider_role, "parts": parts})

    system_instruction = {"parts": system_parts} if system_parts else None
    return contents, system_instruction


def _coerce_attr(obj: object, name: str):
    """Récupère un attribut ou une clé de dict sans lever d'exception."""

    if isinstance(obj, dict):
        return obj.get(name)
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _safety_settings() -> List[object]:
    """Construit la liste des catégories disponibles dans la version du SDK."""

    if HarmCategory is None or HarmBlockThreshold is None:
        return []

    desired = [
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
        "HARM_CATEGORY_CIVIC_INTEGRITY",
    ]

    safety: List[object] = []
    missing: List[str] = []
    for name in desired:
        try:
            category = getattr(HarmCategory, name)
        except AttributeError:
            missing.append(name)
            continue
        if category is None:
            missing.append(name)
            continue
        safety.append({"category": category, "threshold": HarmBlockThreshold.BLOCK_NONE})

    if missing:
        logger.warning(
            "Catégories de sécurité Gemini indisponibles dans ce SDK : %s",
            ", ".join(missing),
        )

    return safety


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

    def generate(
        self, messages: Sequence[dict], *, max_tokens: int, temperature: float
    ) -> str:
        """Déclenche une génération Gemini en convertissant les messages internes."""

        self._ensure_client()
        contents, system_instruction = _messages_to_payload(messages)
        if not contents:
            raise ValueError("Prompt vide pour Gemini")

        model = genai.GenerativeModel(self.model)
        safety_settings = _safety_settings()
        params = {
            "generation_config": {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
            "safety_settings": safety_settings or None,
        }

        supports_system = "system_instruction" in inspect.signature(
            model.generate_content
        ).parameters
        if supports_system and system_instruction:
            params["system_instruction"] = system_instruction
        elif system_instruction and system_instruction.get("parts"):
            # Repli pour les versions du SDK qui ne supportent pas system_instruction :
            # on injecte l'instruction système comme premier message de contenu
            # en la présentant comme une requête utilisateur (Gemini n'accepte que
            # les rôles user/model).
            contents = [
                {"role": "user", "parts": system_instruction.get("parts", [])}
            ] + contents

        response = model.generate_content(contents, **params)
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

        # Certaines versions renvoient un champ output_text uniquement
        # lorsqu'une réponse textuelle est disponible.
        output_text = _coerce_attr(response, "output_text")
        if isinstance(output_text, str) and output_text:
            return output_text

        candidates = getattr(response, "candidates", None)
        if isinstance(candidates, Sequence):
            texts: List[str] = []
            blocked = False
            blocked_reasons: List[str] = []
            finish_reasons: List[str] = []
            feedback_reasons: List[str] = []

            for candidate in candidates:
                safety = _coerce_attr(candidate, "safety_ratings")
                if safety:
                    for rating in safety:
                        category = _coerce_attr(rating, "category")
                        blocked_flag = _coerce_attr(rating, "blocked")
                        if bool(blocked_flag):
                            blocked = True
                            if isinstance(category, str) and category:
                                blocked_reasons.append(category)
                        elif isinstance(category, str) and category:
                            # Même non bloqué, on conserve les catégories pour le diagnostic.
                            blocked_reasons.append(category)

                finish_reason = _coerce_attr(candidate, "finish_reason")
                if isinstance(finish_reason, str) and finish_reason:
                    finish_reasons.append(finish_reason)

                content = _coerce_attr(candidate, "content")
                parts = _coerce_attr(content, "parts") if content else None
                if not parts:
                    parts = _coerce_attr(candidate, "parts")
                if isinstance(parts, Sequence):
                    for part in parts:
                        text_part = _coerce_attr(part, "text")
                        if isinstance(text_part, str) and text_part:
                            texts.append(text_part)
                        elif isinstance(part, dict) and isinstance(part.get("text"), str):
                            if part["text"]:
                                texts.append(part["text"])

            if not candidates and isinstance(response, dict):
                candidates = response.get("candidates")  # type: ignore[assignment]

            prompt_feedback = _coerce_attr(response, "prompt_feedback")
            if isinstance(prompt_feedback, dict):
                reasons = prompt_feedback.get("safety_ratings")
                if isinstance(reasons, Sequence):
                    for rating in reasons:
                        if isinstance(rating, dict):
                            category = rating.get("category")
                            if isinstance(category, str) and category:
                                feedback_reasons.append(category)

            if isinstance(candidates, Sequence) and not texts:
                for candidate in candidates:
                    if isinstance(candidate, dict):
                        finish_reason = candidate.get("finish_reason")
                        if isinstance(finish_reason, str) and finish_reason:
                            finish_reasons.append(finish_reason)
                        safety = candidate.get("safety_ratings")
                        if isinstance(safety, Sequence):
                            for rating in safety:
                                if isinstance(rating, dict):
                                    category = rating.get("category")
                                    blocked_flag = rating.get("blocked")
                                    if blocked_flag:
                                        blocked = True
                                    if isinstance(category, str) and category:
                                        blocked_reasons.append(category)
                        content = candidate.get("content")
                        if isinstance(content, dict):
                            parts = content.get("parts")
                            if isinstance(parts, Sequence):
                                for part in parts:
                                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                                        if part["text"]:
                                            texts.append(part["text"])
                        parts = candidate.get("parts")
                        if isinstance(parts, Sequence):
                            for part in parts:
                                if isinstance(part, dict) and isinstance(part.get("text"), str):
                                    if part["text"]:
                                        texts.append(part["text"])

            if texts:
                return "".join(texts).strip()

            reason_chunks: List[str] = []
            if blocked_reasons:
                reason_chunks.append(
                    "raisons de sécurité : " + ", ".join(sorted(set(blocked_reasons)))
                )
            if feedback_reasons:
                reason_chunks.append(
                    "feedback sécurité : " + ", ".join(sorted(set(feedback_reasons)))
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
