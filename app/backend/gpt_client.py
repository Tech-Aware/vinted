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
from dataclasses import dataclass, replace
from typing import Iterable, List, Optional, Sequence

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


class ListingGenerator:
    """Generate a Vinted listing from encoded images and user comments."""

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
    ) -> None:
        self.model = model or os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not 0 <= temperature <= 1:
            raise ValueError("La température doit être comprise entre 0 et 1")
        self.temperature = temperature
        self._client: Optional[OpenAI] = None
        logger.step(
            "ListingGenerator initialisé avec le modèle %s et une température de %.2f",
            self.model,
            self.temperature,
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
            self._client = OpenAI(api_key=api_key)
            logger.success("Client OpenAI initialisé")
        return self._client

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
                            "les commentaires."
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
            user_content.append({
                "type": "input_text",
                "text": f"Commentaires utilisateur (tâches/défauts): {user_comment}",
            })
            logger.info("Commentaire utilisateur ajouté au prompt (%d caractère(s))", len(user_comment))
        else:
            logger.info("Aucun commentaire utilisateur fourni")
        structured_prompt = f"{template.prompt}\n\n{ListingFields.json_instruction(template.name)}"
        user_content.append({"type": "input_text", "text": structured_prompt})
        logger.step("Template de description ajouté au prompt")
        messages.append({"role": "user", "content": user_content})
        return messages

    def generate_listing(
        self, encoded_images: Iterable[str], user_comment: str, template: ListingTemplate
    ) -> ListingResult:
        logger.step("Début de la génération d'annonce")
        encoded_images_list = list(encoded_images)
        try:
            messages = self._build_messages(encoded_images_list, user_comment, template)
            response = self.client.responses.create(
                model=self.model,
                input=messages,
                max_output_tokens=700,
                temperature=self.temperature,
            )
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
            logger.step("Récupération ciblée du SKU polaire")
            recovered_sku_raw = self._recover_polaire_sku(encoded_images_list, user_comment)
            recovered_sku_raw = (recovered_sku_raw or "").strip()
            fenced = re.fullmatch(r"```[a-zA-Z0-9_-]*\s*(.*?)\s*```", recovered_sku_raw, re.DOTALL)
            if fenced:
                recovered_sku_raw = fenced.group(1)
            match = re.search(r"(PTNF|PC)-\d{1,3}", recovered_sku_raw, re.IGNORECASE)
            if not match:
                raise ValueError(
                    "Impossible de récupérer un SKU polaire lisible. "
                    "Merci de fournir la référence dans le commentaire ou des photos plus nettes."
                )
            recovered_sku = match.group(0).strip().upper()
            fields = replace(fields, sku=recovered_sku)

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
            response = self.client.responses.create(
                model=self.model,
                input=messages,
                max_output_tokens=50,
                temperature=0.0,
            )
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
            response = self.client.responses.create(
                model=self.model,
                input=messages,
                max_output_tokens=50,
                temperature=0.0,
            )
        except Exception:
            logger.exception("Échec de la récupération ciblée du SKU polaire")
            raise

        return self._extract_response_text(response)

    def _extract_response_text(self, response: object) -> str:
        """Extract textual content from the OpenAI response payload."""

        parts: List[str] = []

        def _append_if_text(value: object) -> None:
            text = self._coerce_text(value)
            if text:
                parts.append(text)

        # First try the pydantic representation when available
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
