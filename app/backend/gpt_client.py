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

"""Wrapper around OpenAI's API to generate Vinted listing content."""

import json
import os
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Iterable, List, Optional, Sequence

import httpx

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from app.logger import get_logger
from app.backend.listing_fields import ListingFields
from app.backend.templates import ListingTemplate


logger = get_logger(__name__)


@dataclass
class ListingResult:
    """Result returned by the listing generator."""

    title: str
    description: str
    sku_missing: bool = False
    price_estimate: Optional[str] = None


_FR_SIZE_OVERRIDE_PATTERN = re.compile(
    r"(?i)\b(?:fr\s*-?\s*(\d{2,3})|(\d{2,3})\s*fr|taille\s*(?:fr\s*)?(\d{2,3}))\b"
)
_US_SIZE_PATTERN = re.compile(
    r"(?i)\b(?:us\s*(?:w\s*)?(\d{1,2})(?:\s*[x/]*\s*l?\s*(\d{1,2}))?|w\s*(\d{1,2})\s*l\s*(\d{1,2}))\b"
)

def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


class ListingGenerator:
    """Generate a Vinted listing from encoded images and user comments."""

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.4,
        response_temperature: float = 0.3,
    ) -> None:
        self.model = model or os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.temperature = self._validate_temperature(temperature)
        self.response_temperature = self._validate_temperature(response_temperature)
        self._client: Optional[OpenAI] = None
        logger.step(
            (
                "ListingGenerator initialisé avec le modèle %s (annonces: %.2f, "
                "réponses clients: %.2f)"
            ),
            self.model,
            self.temperature,
            self.response_temperature,
        )

    @property
    def client(self) -> OpenAI:
        if OpenAI is None:
            logger.error("Le package 'openai' est requis mais non disponible")
            raise RuntimeError(
                "Le package 'openai' est requis. Installez-le via 'pip install openai'."
            )
        if self._client is None:
            api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("Clé API OpenAI manquante")
                raise RuntimeError(
                    "Clé API OpenAI manquante. Définissez la variable d'environnement OPENAI_API_KEY."
                )
            # httpx>=0.28 renomme l'argument "proxies" en "proxy". Le client OpenAI
            # tente d'instancier httpx avec "proxies" par défaut, ce qui provoque
            # une erreur de type. On fournit donc explicitement un http_client
            # compatible pour éviter l'incompatibilité de signature.
            http_client = httpx.Client(trust_env=True)
            self._client = OpenAI(api_key=api_key, http_client=http_client)
            logger.success("Client OpenAI initialisé")
        return self._client

    @staticmethod
    def _validate_temperature(value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("La température doit être comprise entre 0 et 1")
        return value

    def _build_messages(
        self,
        encoded_images: Iterable[str],
        user_comment: str,
        template: ListingTemplate,
    ) -> List[dict]:
        logger.step("Construction du prompt pour l'API OpenAI")
        images_list = list(encoded_images)
        messages: List[dict] = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Tu es un assistant vendeur Vinted. Analyse les photos fournies, "
                            "identifie uniquement les caractéristiques visibles ou confirmées (taille, couleur, défauts) "
                            "et produis un titre et une description suivant le template donné. Ne fais aucune supposition "
                            "ni estimation : laisse un champ vide lorsqu'une information n'est pas prouvée par les photos ou "
                            "les commentaires. Les informations saisies dans la boîte Commentaire priment sur tout le reste "
                            "pour remplir les champs, calculer l'estimation de prix et rédiger l'annonce."
                        ),
                    }
                ],
            }
        ]
        user_content: List[dict] = []
        for image in images_list:
            user_content.append(
                {
                    "type": "input_image",
                    "image_url": image,
                }
            )
        logger.info("%d image(s) intégrée(s) dans le prompt", len(images_list))
        if user_comment:
            logger.info(
                "Commentaire utilisateur ignoré par le prompt direct (%d caractère(s)),"
                " application différée via overrides",
                len(user_comment),
            )
        else:
            logger.info("Aucun commentaire utilisateur fourni")
        structured_prompt = f"{template.prompt}\n\n{ListingFields.json_instruction(template.name)}"
        user_content.append({"type": "input_text", "text": structured_prompt})
        logger.step("Template de description ajouté au prompt")
        messages.append({"role": "user", "content": user_content})
        return messages

    def generate_listing(
        self,
        encoded_images: Iterable[str],
        user_comment: str,
        template: ListingTemplate,
        fr_size_override: str,
        us_size_override: Optional[str] = None,
        manual_sku: Optional[str] = None,
    ) -> ListingResult:
        logger.step("Début de la génération d'annonce")
        encoded_images_list = list(encoded_images)
        try:
            messages = self._build_messages(encoded_images_list, user_comment, template)
            response = self._create_response(messages, max_tokens=700)
        except Exception:
            logger.exception("Échec de l'appel à l'API OpenAI")
            raise
        logger.success("Réponse reçue depuis l'API OpenAI")
        content = self._extract_response_text(response)
        if not content:
            friendly_message = (
                "Aucune réponse textuelle n'a été renvoyée par le modèle. "
                "Merci de réessayer dans quelques instants."
            )
            logger.error(friendly_message)
            raise ValueError(friendly_message)
        fenced_match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if fenced_match:
            content_to_parse = fenced_match.group(1).strip()
        else:
            content_to_parse = content.strip()
        logger.step("Analyse de la réponse JSON")
        try:
            payload = json.loads(content_to_parse)
            fields_payload = payload.get("fields")
            if not isinstance(fields_payload, dict):
                raise ValueError("Structure JSON invalide: clé 'fields' manquante ou incorrecte")
            fields = ListingFields.from_dict(
                fields_payload, template_name=template.name
            )
        except Exception as exc:
            template_name = template.name or ""
            if (
                isinstance(exc, ValueError)
                and "SKU invalide" in str(exc)
                and template_name.startswith("template-jean-levis")
            ):
                logger.warning(
                    "SKU Levi's invalide renvoyé par le modèle, application du fallback",
                )
                sanitized_payload = dict(fields_payload)
                sanitized_payload["sku"] = ""
                fields = ListingFields.from_dict(
                    sanitized_payload, template_name=template.name
                )
            else:
                logger.exception("Échec de l'analyse de la réponse JSON")
                snippet = content_to_parse[:200]
                raise ValueError(
                    "Réponse du modèle invalide, impossible de parser le JSON (extrait: %s)" % snippet
                ) from exc

        fields = self._apply_user_overrides(
            user_comment,
            fields,
            fr_size_override=fr_size_override,
            us_size_override=us_size_override,
            manual_sku=manual_sku,
        )

        if template.name == "template-pull-tommy-femme" and not (fields.sku and fields.sku.strip()):
            logger.step("Récupération ciblée du SKU Tommy Hilfiger")
            recovered_sku_raw = self._recover_tommy_sku(encoded_images_list, user_comment)
            recovered_sku_raw = (recovered_sku_raw or "").strip()
            fenced = re.fullmatch(r"```[a-zA-Z0-9_-]*\s*(.*?)\s*```", recovered_sku_raw, re.DOTALL)
            if fenced:
                recovered_sku_raw = fenced.group(1)
            match = re.search(r"PTF\d{1,3}", recovered_sku_raw, re.IGNORECASE)
            if not match:
                raise ValueError(
                    "Impossible de récupérer un SKU Tommy Hilfiger lisible. "
                    "Merci de fournir la référence dans le commentaire ou des photos plus nettes."
                )
            recovered_sku = match.group(0).strip().upper()
            fields = replace(fields, sku=recovered_sku)

        if template.name == "template-polaire-outdoor" and not (fields.sku and fields.sku.strip()):
            labels_support_sku = fields.fabric_label_visible or fields.non_size_labels_visible
            if labels_support_sku:
                logger.warning(
                    "SKU polaire manquant malgré des étiquettes visibles : aucune récupération automatique",
                )
            else:
                logger.warning(
                    "SKU polaire manquant et étiquettes invisibles : signalement sans récupération"
                )
        title, description, price_estimate = template.render(fields)
        logger.success("Titre et description générés depuis les données structurées")

        sku_missing = not bool(fields.sku and fields.sku.strip())
        if sku_missing:
            logger.warning("SKU absent des données générées, signalement au frontal")

        return ListingResult(
            title=title,
            description=description,
            sku_missing=sku_missing,
            price_estimate=price_estimate,
        )

    def _apply_user_overrides(
        self,
        user_comment: str,
        fields: ListingFields,
        *,
        fr_size_override: Optional[str] = None,
        us_size_override: Optional[str] = None,
        manual_sku: Optional[str] = None,
    ) -> ListingFields:
        """Force model fields with explicit user instructions."""

        size_overridden = False
        us_size_mentioned = False
        explicit_overrides: dict = {}

        if manual_sku and manual_sku.strip():
            explicit_overrides["sku"] = manual_sku.strip()
            logger.step("SKU renseigné manuellement, application de la valeur fournie")

        if fr_size_override:
            explicit_overrides["fr_size"] = fr_size_override.strip()
            explicit_overrides["size_label_visible"] = True
            size_overridden = True

        if us_size_override:
            explicit_overrides["us_w"] = us_size_override.strip()
            us_size_mentioned = True

        if not user_comment:
            if explicit_overrides:
                fields = replace(fields, **explicit_overrides)
                if size_overridden and not us_size_mentioned:
                    fields = replace(fields, us_w="", us_l="")
                if size_overridden:
                    fields = replace(
                        fields,
                        waist_measurement_cm=None,
                        waist_flat_measurement_cm=None,
                    )
            return self._strip_inferred_sizes(fields, size_overridden=size_overridden)

        (
            overrides,
            leftover_notes,
            comment_size_overridden,
            comment_us_size_mentioned,
        ) = self._extract_overrides_from_comment(user_comment)
        size_overridden = size_overridden or comment_size_overridden
        us_size_mentioned = us_size_mentioned or comment_us_size_mentioned

        overrides = {**overrides, **explicit_overrides}

        if leftover_notes:
            existing_notes = (fields.feature_notes or "").strip()
            merged_notes = ", ".join(note for note in leftover_notes if note)
            if merged_notes:
                deduped_notes: list[str] = []
                seen = set()
                for part in re.split(r"[,;\n]+", ", ".join((existing_notes, merged_notes))):
                    cleaned = part.strip()
                    folded = cleaned.casefold()
                    if cleaned and folded not in seen:
                        seen.add(folded)
                        deduped_notes.append(cleaned)

                if deduped_notes:
                    overrides["feature_notes"] = ", ".join(deduped_notes)

        if overrides:
            logger.info(
                "Application des overrides depuis le commentaire: %s",
                ", ".join(sorted(overrides)),
            )
            fields = replace(fields, **overrides)
            if size_overridden and not us_size_mentioned:
                # Lorsque l'utilisateur impose une taille FR, on neutralise W/L
                # pour éviter qu'une conversion automatique ne remplace sa valeur.
                fields = replace(fields, us_w="", us_l="")
            if size_overridden:
                fields = replace(
                    fields,
                    waist_measurement_cm=None,
                    waist_flat_measurement_cm=None,
                )

        return self._strip_inferred_sizes(fields, size_overridden=size_overridden)

    @staticmethod
    def _extract_fr_size_override(user_comment: str) -> Optional[str]:
        match = _FR_SIZE_OVERRIDE_PATTERN.search(user_comment)
        if not match:
            return None

        for group in match.groups():
            if group:
                return group.strip()
        return None

    def _extract_overrides_from_comment(
        self, user_comment: str
    ) -> tuple[dict, list[str], bool, bool]:
        """Parse the free-form comment to override structured fields.

        Returns a tuple of (overrides, leftover_notes, size_overridden,
        us_size_mentioned). "overrides" contains direct field replacements
        (e.g. taille, couleur, marque) while "leftover_notes" gathers
        unclassified pieces of information to append to the feature notes
        section instead of polluting the title.
        """

        overrides: dict = {}
        leftover_notes: list[str] = []

        size_overridden = False
        us_size_mentioned = bool(_US_SIZE_PATTERN.search(user_comment))

        fr_size_override = self._extract_fr_size_override(user_comment)
        if fr_size_override:
            overrides["fr_size"] = fr_size_override
            size_overridden = True

        # Découpe les instructions séparées par des virgules ou retours à la ligne
        segments = [
            segment.strip()
            for segment in re.split(r"[,\n;]+", user_comment)
            if segment.strip()
        ]

        for segment in segments:
            lower = segment.lower()
            normalized = _normalize_text(segment)
            key_value_match = re.match(r"\s*(\w[\w\s]+?)\s*[:\-]\s*(.+)", segment)

            if lower.startswith("taille"):
                # Already captured by the global regex, but keep the content as note otherwise
                if fr_size_override:
                    continue
            if lower.startswith("couleur") or lower.startswith("coloris"):
                color_value = segment.split(":", 1)[-1] if ":" in segment else segment
                color_value = color_value.split("-", 1)[-1].strip()
                if color_value:
                    overrides["color_main"] = color_value
                    continue

            if lower.startswith("marque"):
                brand_value = segment.split(":", 1)[-1].strip() if ":" in segment else ""
                if brand_value:
                    overrides["brand"] = brand_value
                    continue

            if lower.startswith("modele") or lower.startswith("modèle"):
                model_value = segment.split(":", 1)[-1].strip() if ":" in segment else ""
                if model_value:
                    overrides["model"] = model_value
                    continue

            if lower.startswith("defaut") or lower.startswith("défaut"):
                defect_value = segment.split(":", 1)[-1].strip() if ":" in segment else ""
                if defect_value:
                    overrides["defects"] = defect_value
                    continue

            if "defects" not in overrides and any(
                keyword in normalized
                for keyword in (
                    "defaut",
                    "defauts",
                    "tache",
                    "taches",
                    "tachee",
                    "tachees",
                    "taché",
                    "tachés",
                    "tachée",
                    "tachées",
                )
            ):
                overrides["defects"] = segment
                continue

            if key_value_match:
                # Catch-all: clé/valeur non reconnue => note
                leftover_notes.append(segment)
                continue

            leftover_notes.append(segment)

        return overrides, leftover_notes, size_overridden, us_size_mentioned

    @staticmethod
    def _strip_inferred_sizes(
        fields: ListingFields, *, size_overridden: bool
    ) -> ListingFields:
        """Remove size labels hallucinated without a visible tag.

        The vision model sometimes renvoie des tailles même lorsque
        ``size_label_visible`` est ``False``. Pour éviter des erreurs
        dans le rendu et respecter la consigne « ne rien inventer »,
        on purge les tailles générées si l'utilisateur n'a pas fourni
        d'override explicite.
        """

        if size_overridden or fields.size_label_visible:
            return fields

        if (fields.fr_size or fields.us_w or fields.us_l) and not size_overridden:
            logger.info(
                "Suppression des tailles retournées sans étiquette visible (FR/US/WL)",
            )
            return replace(fields, fr_size="", us_w="", us_l="")

        return fields

    def _recover_tommy_sku(
        self, encoded_images: Sequence[str], user_comment: str
    ) -> str:
        """Run a targeted prompt to recover the Tommy Hilfiger SKU."""

        user_content: List[dict] = []
        for image in encoded_images:
            user_content.append({"type": "input_image", "image_url": image})

        prompt_lines = [
            "Analyse uniquement les photos ci-dessus.",
            "Repère le SKU Tommy Hilfiger au format PTF suivi de 1 à 3 chiffres.",
            "Si tu lis clairement ce code, réponds uniquement avec ce SKU exact.",
            "Si aucun code n'est lisible, réponds avec une chaîne vide sans autre texte.",
        ]
        if user_comment:
            prompt_lines.append(
                "Ignore les spéculations du commentaire utilisateur sauf s'il confirme explicitement le SKU."
            )

        user_content.append({"type": "input_text", "text": "\n".join(prompt_lines)})

        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Tu es un assistant vendeur Vinted. Retourne uniquement le SKU Tommy Hilfiger demandé."
                        ),
                    }
                ],
            },
            {"role": "user", "content": user_content},
        ]

        try:
            response = self._create_response(messages, max_tokens=50)
        except Exception:
            logger.exception("Échec de la récupération ciblée du SKU Tommy Hilfiger")
            raise

        return self._extract_response_text(response)

    def _recover_polaire_sku(
        self, encoded_images: Sequence[str], user_comment: str
    ) -> str:
        """Run a targeted prompt to recover the polaire SKU."""

        user_content: List[dict] = []
        for image in encoded_images:
            user_content.append({"type": "input_image", "image_url": image})

        prompt_lines = [
            "Analyse uniquement les photos ci-dessus.",
            "Repère un SKU polaire au format PTNF-n (1 à 3 chiffres) pour The North Face ou PC-n pour Columbia.",
            "Si tu lis clairement ce code, réponds uniquement avec ce SKU exact.",
            "Si aucun code n'est lisible, réponds avec une chaîne vide sans autre texte.",
        ]
        if user_comment:
            prompt_lines.append(
                "Ignore les spéculations du commentaire utilisateur sauf s'il confirme explicitement le SKU."
            )

        user_content.append({"type": "input_text", "text": "\n".join(prompt_lines)})

        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Tu es un assistant vendeur Vinted. Retourne uniquement le SKU polaire demandé."
                        ),
                    }
                ],
            },
            {"role": "user", "content": user_content},
        ]

        try:
            response = self._create_response(messages, max_tokens=50)
        except Exception:
            logger.exception("Échec de la récupération ciblée du SKU polaire")
            raise

        return self._extract_response_text(response)

    def _create_response(self, messages: Sequence[dict], *, max_tokens: int):
        """Call OpenAI using either the new responses API or chat completions."""

        client = self.client
        if hasattr(client, "responses"):
            return client.responses.create(
                model=self.model,
                input=messages,
                max_output_tokens=max_tokens,
                temperature=self.temperature,
            )

        chat_messages = self._convert_to_chat_messages(messages)
        return client.chat.completions.create(
            model=self.model,
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=self.temperature,
        )

    def _convert_to_chat_messages(self, messages: Sequence[dict]) -> List[dict]:
        chat_messages: List[dict] = []
        for message in messages:
            content_parts = []
            for part in message.get("content", []):
                part_type = part.get("type")
                if part_type in {"input_text", "text"}:
                    content_parts.append({"type": "text", "text": part.get("text", "")})
                elif part_type in {"input_image", "image_url"}:
                    url = part.get("image_url")
                    if isinstance(url, dict):
                        url_value = url.get("url") or url.get("uri")
                    else:
                        url_value = url
                    if url_value:
                        content_parts.append({"type": "image_url", "image_url": {"url": url_value}})
            if not content_parts:
                content_parts.append({"type": "text", "text": ""})
            chat_messages.append({"role": message.get("role", "user"), "content": content_parts})
        return chat_messages

    def _extract_response_text(self, response: object) -> str:
        """Extract textual content from the OpenAI response payload."""

        parts: List[str] = []

        def _append_if_text(value: object) -> None:
            text = self._coerce_text(value)
            if text:
                parts.append(text)

        # First try the pydantic representation when available (responses API)
        if hasattr(response, "model_dump"):
            try:
                dumped = response.model_dump()  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive programming
                dumped = None
            if isinstance(dumped, dict):
                output_blocks = dumped.get("output")
                if isinstance(output_blocks, Sequence):
                    for block in output_blocks:
                        contents = None
                        if isinstance(block, dict):
                            contents = block.get("content")
                        if isinstance(contents, Sequence):
                            for item in contents:
                                if isinstance(item, dict):
                                    _append_if_text(item.get("text"))
                if not parts:
                    _append_if_text(dumped.get("output_text"))

        # Fallback for chat.completions format
        if not parts and hasattr(response, "choices"):
            choices = getattr(response, "choices", [])
            if isinstance(choices, Sequence):
                for choice in choices:
                    message = getattr(choice, "message", None)
                    if message and hasattr(message, "content"):
                        _append_if_text(message.content)
                    if hasattr(choice, "text"):
                        _append_if_text(getattr(choice, "text"))

        if not parts:
            output = getattr(response, "output", None)
            if isinstance(output, Sequence):
                for block in output:
                    content_items = getattr(block, "content", None)
                    if isinstance(content_items, Sequence):
                        for item in content_items:
                            _append_if_text(getattr(item, "text", None))
            if not parts:
                _append_if_text(getattr(response, "output_text", None))

        return "".join(part for part in parts if part).strip()

    @staticmethod
    def _coerce_text(value: object) -> str:
        """Convert various text container shapes into a string."""

        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if hasattr(value, "value"):
            inner = getattr(value, "value")
            if isinstance(inner, str):
                return inner
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            collected: List[str] = []
            for item in value:
                text = ListingGenerator._coerce_text(getattr(item, "text", item))
                if text:
                    collected.append(text)
            return "".join(collected)
        text_attr = getattr(value, "text", None)
        if isinstance(text_attr, str):
            return text_attr
        if hasattr(text_attr, "value"):
            inner = getattr(text_attr, "value")
            if isinstance(inner, str):
                return inner
        return ""
