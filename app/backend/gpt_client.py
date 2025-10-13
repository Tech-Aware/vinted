"""Wrapper around OpenAI's API to generate Vinted listing content."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore


@dataclass
class ListingResult:
    """Result returned by the listing generator."""

    title: str
    description: str


class ListingGenerator:
    """Generate a Vinted listing from encoded images and user comments."""

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if OpenAI is None:
            raise RuntimeError(
                "Le package 'openai' est requis. Installez-le via 'pip install openai'."
            )
        if self._client is None:
            api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "Clé API OpenAI manquante. Définissez la variable d'environnement OPENAI_API_KEY."
                )
            self._client = OpenAI(api_key=api_key)
        return self._client

    def _build_messages(
        self,
        encoded_images: Iterable[str],
        user_comment: str,
        template_prompt: str,
    ) -> List[dict]:
        messages: List[dict] = [
            {
                "role": "system",
                "content": (
                    "Tu es un assistant vendeur Vinted. Analyse les photos fournies, "
                    "identifie les caractéristiques importantes (taille, couleur, défauts) et "
                    "produis un titre et une description suivant le template donné."
                ),
            }
        ]
        user_content: List[dict] = []
        for image in encoded_images:
            user_content.append({
                "type": "input_image",
                "image_base64": image,
            })
        if user_comment:
            user_content.append({
                "type": "text",
                "text": f"Commentaires utilisateur (tâches/défauts): {user_comment}",
            })
        user_content.append({"type": "text", "text": template_prompt})
        messages.append({"role": "user", "content": user_content})
        return messages

    def generate_listing(
        self, encoded_images: Iterable[str], user_comment: str, template_prompt: str
    ) -> ListingResult:
        messages = self._build_messages(encoded_images, user_comment, template_prompt)
        response = self.client.responses.create(
            model=self.model,
            input=messages,
            max_output_tokens=700,
            temperature=0.7,
        )
        content = ""
        output = getattr(response, "output", None)
        if output:
            for block in output:
                for item in getattr(block, "content", []):
                    text = getattr(item, "text", None)
                    if text:
                        content += text
        if not content:
            content = getattr(response, "output_text", "").strip()
        content = content.strip()
        title_marker = "TITRE"
        description_marker = "DESCRIPTION"
        title = content
        description = ""
        if title_marker in content and description_marker in content:
            _, rest = content.split(title_marker, 1)
            title_text, desc_block = rest.split(description_marker, 1)
            title = title_text.strip().replace("\n", " ")
            description = desc_block.strip()
        else:
            lines = content.splitlines()
            if lines:
                title = lines[0].strip()
                description = "\n".join(line.strip() for line in lines[1:]).strip()
        return ListingResult(title=title, description=description)
