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
from dataclasses import dataclass
from typing import Iterable, List, Optional

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


class ListingGenerator:
    """Generate a Vinted listing from encoded images and user comments."""

    def __init__(self, *, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.model = model or os.getenv("OPENAI_VISION_MODEL", "gpt-4.1")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client: Optional[OpenAI] = None
        logger.step("ListingGenerator initialisé avec le modèle %s", self.model)

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
                            "identifie les caractéristiques importantes (taille, couleur, défauts) et "
                            "produis un titre et une description suivant le template donné."
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
        structured_prompt = f"{template.prompt}\n\n{ListingFields.json_instruction()}"
        user_content.append({"type": "input_text", "text": structured_prompt})
        logger.step("Template de description ajouté au prompt")
        messages.append({"role": "user", "content": user_content})
        return messages

    def generate_listing(
        self, encoded_images: Iterable[str], user_comment: str, template: ListingTemplate
    ) -> ListingResult:
        logger.step("Début de la génération d'annonce")
        try:
            messages = self._build_messages(encoded_images, user_comment, template)
            response = self.client.responses.create(
                model=self.model,
                input=messages,
                max_output_tokens=700,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
        except Exception:
            logger.exception("Échec de l'appel à l'API OpenAI")
            raise
        logger.success("Réponse reçue depuis l'API OpenAI")
        content = (getattr(response, "output_text", "") or "").strip()
        if not content:
            output = getattr(response, "output", None)
            if output:
                for block in output:
                    for item in getattr(block, "content", []):
                        text = getattr(item, "text", None)
                        if text:
                            content += text
                content = content.strip()
        logger.step("Analyse de la réponse JSON")
        try:
            payload = json.loads(content)
            fields_payload = payload.get("fields")
            if not isinstance(fields_payload, dict):
                raise ValueError("Structure JSON invalide: clé 'fields' manquante ou incorrecte")
            fields = ListingFields.from_dict(fields_payload)
        except Exception as exc:
            logger.exception("Échec de l'analyse de la réponse JSON")
            raise ValueError("Réponse du modèle invalide, impossible de parser le JSON") from exc

        title, description = template.render(fields)
        logger.success("Titre et description générés depuis les données structurées")
        return ListingResult(title=title, description=description)
