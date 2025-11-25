from __future__ import annotations

"""
Tools for generating tailored customer replies based on predefined scenarios.
"""

import os
from dataclasses import dataclass
from textwrap import dedent
from typing import Dict, List, Optional, Sequence

import httpx

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from app.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ArticleType:
    id: str
    label: str


@dataclass(frozen=True)
class ScenarioConfig:
    id: str
    label: str
    requires_client_message: bool
    extra_fields: Sequence[str]
    rules: Sequence[str]


@dataclass
class CustomerReplyPayload:
    article_type: str
    scenario_id: str
    client_message: str = ""
    prix_initial: Optional[float] = None
    prix_propose_client: Optional[float] = None
    prix_min_accepte: Optional[float] = None
    delai_envoi_habituel: str = ""
    taille_fr: str = ""
    equivalence_w: str = ""


ARTICLE_TYPES: Sequence[ArticleType] = (
    ArticleType("jean_levis", "Jean Levi's"),
    ArticleType("pull_tommy", "Pull Tommy Hilfiger"),
    ArticleType("jacket", "Jacket / Veste"),
    ArticleType("polaire_tnf", "Polaire The North Face"),
    ArticleType("polaire_columbia", "Polaire Columbia"),
    ArticleType("autre", "Autre article"),
)


EXTRA_FIELD_LABELS: Dict[str, str] = {
    "prix_initial": "Prix initial",
    "prix_propose_client": "Offre du client",
    "prix_min_accepte": "Prix minimum accepté",
    "delai_envoi_habituel": "Délai d'envoi habituel",
    "taille_fr": "Taille FR",
    "equivalence_w": "Équivalence W",
}


SCENARIOS: Dict[str, ScenarioConfig] = {
    "reservation_incitation": ScenarioConfig(
        id="reservation_incitation",
        label="1) Demande de réservation → incitation à acheter",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Ton chaleureux et positif.",
            "Pas de réservation longue ; encourager l'achat direct tant que l'article est dispo.",
            "2 à 3 phrases maximum.",
            "Clore par une invitation légère à visiter le dressing.",
        ),
    ),
    "contre_offre_19_12_17": ScenarioConfig(
        id="contre_offre_19_12_17",
        label="2) Contre-offre Levi's (19 → 12 → 17)",
        requires_client_message=True,
        extra_fields=["prix_initial", "prix_propose_client", "prix_min_accepte"],
        rules=(
            "Remercier pour l'intérêt.",
            "12€ est trop bas au vu de la qualité ; proposer 17€ comme compromis.",
            "Mentionner le reste du dressing.",
        ),
    ),
    "acceptation_tnf": ScenarioConfig(
        id="acceptation_tnf",
        label="3) Acceptation achat veste The North Face",
        requires_client_message=False,
        extra_fields=["delai_envoi_habituel"],
        rules=(
            "Remercier pour l'achat.",
            "Promettre un envoi rapide et partage du suivi.",
            "Style sobre, 2–3 phrases, peu ou pas d'émojis.",
        ),
    ),
    "urgence_adidas": ScenarioConfig(
        id="urgence_adidas",
        label="4) Message urgent coupe-vent Adidas",
        requires_client_message=False,
        extra_fields=["delai_envoi_habituel"],
        rules=(
            "Article très demandé / beaucoup de vues.",
            "Souligner l'unicité de la pièce et encourager à valider vite.",
            "Glisser l'info expédition rapide.",
            "Ton dynamique sans agressivité, 2–3 phrases.",
        ),
    ),
    "remerciement_levi_515": ScenarioConfig(
        id="remerciement_levi_515",
        label="5) Remerciement achat Levi's 515",
        requires_client_message=False,
        extra_fields=["delai_envoi_habituel"],
        rules=(
            "Remercier pour l'achat.",
            "Indiquer préparation rapide et partage du suivi.",
            "Invitation légère à consulter le dressing.",
        ),
    ),
    "contre_offre_20_12_17": ScenarioConfig(
        id="contre_offre_20_12_17",
        label="6) Contre-offre Levi's (20 → 12 → 17)",
        requires_client_message=True,
        extra_fields=["prix_initial", "prix_propose_client", "prix_min_accepte"],
        rules=(
            "Remercier pour l'offre.",
            "Valoriser l'état de l'article.",
            "12€ trop bas ; proposer 17€ comme geste commercial.",
        ),
    ),
    "correspondance_46_w34": ScenarioConfig(
        id="correspondance_46_w34",
        label="7) Correspondance taille FR46 → W34",
        requires_client_message=True,
        extra_fields=["taille_fr", "equivalence_w"],
        rules=(
            "Répondre factuellement sur la correspondance FR46 ≈ W34.",
            "Préciser que les mesures sont en photo et conseiller une comparaison avec un jean personnel.",
            "2–3 phrases, ton neutre.",
        ),
    ),
    "relance_favoris": ScenarioConfig(
        id="relance_favoris",
        label="8) Message aux favoris",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Remercier pour l'ajout en favori.",
            "Mentionner que l'article est dispo pour le moment.",
            "Inciter discrètement à finaliser (envoi rapide possible).",
            "Ton doux, 2–3 phrases.",
        ),
    ),
    "remerciement_paiement_attente": ScenarioConfig(
        id="remerciement_paiement_attente",
        label="9) Remerciement achat (paiement en attente)",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Remercier pour l'achat.",
            "Indiquer expédition dès validation du paiement.",
            "Proposer de répondre aux questions.",
        ),
    ),
    "notification_arrivee_colis": ScenarioConfig(
        id="notification_arrivee_colis",
        label="10) Notification d'arrivée du colis",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Informer que le colis est indiqué livré ou en point relais.",
            "Demander confirmation et proposer aide en cas de souci.",
            "Si tout est ok, proposer de laisser un avis.",
        ),
    ),
    "traduction_it_avec_plaisir": ScenarioConfig(
        id="traduction_it_avec_plaisir",
        label="11) Traduction « Avec plaisir » en italien",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Répondre uniquement par 'Con piacere'.",
        ),
    ),
    "refus_prix_ferme_15": ScenarioConfig(
        id="refus_prix_ferme_15",
        label="12) Refus + prix Levi's Premium 15€ ferme",
        requires_client_message=True,
        extra_fields=["prix_min_accepte"],
        rules=(
            "Remercier pour l'intérêt.",
            "Expliquer poliment que le prix est ferme à 15€ pour un modèle premium.",
            "Ton ferme mais respectueux.",
        ),
    ),
    "remerciement_acceptation_offre": ScenarioConfig(
        id="remerciement_acceptation_offre",
        label="13) Remerciement après acceptation d'offre",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Remercier pour l'offre acceptée.",
            "Promettre un envoi rapide et partage du suivi.",
            "Clore par une phrase de disponibilité.",
        ),
    ),
}


def get_article_label(article_type: str) -> str:
    for article in ARTICLE_TYPES:
        if article.id == article_type:
            return article.label
    return article_type or "Article"


class CustomerReplyGenerator:
    """Generate concise, on-brand replies for Vinted customers."""

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.4,
    ) -> None:
        self.model = model or os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not 0 <= temperature <= 1:
            raise ValueError("La température doit être comprise entre 0 et 1")
        self.temperature = temperature
        self._client: Optional[OpenAI] = None
        logger.step(
            "CustomerReplyGenerator initialisé avec le modèle %s et une température de %.2f",
            self.model,
            self.temperature,
        )

    @property
    def client(self) -> OpenAI:
        if OpenAI is None:
            logger.error("Le package 'openai' est requis mais non disponible")
            raise RuntimeError("Installez la dépendance 'openai' pour générer des réponses.")
        if self._client is None:
            api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("Clé API OpenAI manquante pour la génération des réponses")
                raise RuntimeError(
                    "Clé API OpenAI manquante. Définissez la variable d'environnement OPENAI_API_KEY."
                )
            # httpx>=0.28 ne supporte plus l'argument "proxies" attendu par la
            # construction par défaut du client OpenAI. On injecte donc un
            # http_client explicitement compatible pour éviter l'erreur de type.
            http_client = httpx.Client(trust_env=True)
            self._client = OpenAI(api_key=api_key, http_client=http_client)
            logger.success("Client OpenAI initialisé pour les réponses clients")
        return self._client

    def generate_reply(self, payload: CustomerReplyPayload) -> str:
        logger.step("Génération d'une réponse client pour le scénario %s", payload.scenario_id)
        scenario = SCENARIOS.get(payload.scenario_id)
        if scenario is None:
            raise ValueError(f"Scénario inconnu: {payload.scenario_id}")

        prompt = self._build_prompt(payload, scenario)
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Tu es un vendeur professionnel Vinted (Durin31). Tu réponds en français, "
                            "de façon concise (2 à 4 phrases), chaleureuse et orientée client. "
                            "Tu ne promets rien que tu ne puisses tenir. Réponds directement sans puces."
                        ),
                    }
                ],
            },
            {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
        ]

        try:
            response = self._create_response(messages, max_tokens=260)
        except Exception:
            logger.exception("Échec de l'appel OpenAI pour la réponse client")
            raise

        reply = self._extract_response_text(response)
        if not reply:
            friendly_message = (
                "Aucune réponse textuelle n'a été renvoyée par le modèle. Merci de réessayer."
            )
            logger.error(friendly_message)
            raise ValueError(friendly_message)

        logger.success("Réponse client générée avec succès")
        return reply.strip()

    def _build_prompt(self, payload: CustomerReplyPayload, scenario: ScenarioConfig) -> str:
        article_label = get_article_label(payload.article_type)
        context_lines = [f"Scénario: {scenario.label}", f"Article: {article_label}"]
        if payload.client_message:
            context_lines.append(f"Message client: {payload.client_message.strip()}")

        price_details = []
        if payload.prix_initial is not None:
            price_details.append(f"Prix initial: {payload.prix_initial}€")
        if payload.prix_propose_client is not None:
            price_details.append(f"Offre client: {payload.prix_propose_client}€")
        if payload.prix_min_accepte is not None:
            price_details.append(f"Objectif / prix mini: {payload.prix_min_accepte}€")
        if price_details:
            context_lines.append(" / ".join(price_details))

        if payload.delai_envoi_habituel:
            context_lines.append(f"Délai d'envoi habituel: {payload.delai_envoi_habituel}")
        if payload.taille_fr:
            context_lines.append(f"Taille FR renseignée: {payload.taille_fr}")
        if payload.equivalence_w:
            context_lines.append(f"Équivalence W fournie: {payload.equivalence_w}")

        rules = list(scenario.rules)
        if scenario.id in {"contre_offre_19_12_17", "contre_offre_20_12_17"}:
            rules.append(
                "Si l'offre du client atteint ou dépasse le prix minimum accepté, accepter directement."
            )
        if scenario.id == "traduction_it_avec_plaisir":
            rules.append("Réponds uniquement par la traduction demandée, sans signe superflu.")

        prompt = dedent(
            """
            Contexte client et article:
            {context}

            Règles spécifiques:
            - {rules}

            Rédige la réponse finale en suivant le ton Durin31.
            """
        ).format(context="\n".join(context_lines), rules="\n- ".join(rules))

        logger.info("Prompt de réponse client construit (%d caractères)", len(prompt))
        return prompt.strip()

    def _create_response(self, messages: Sequence[dict], *, max_tokens: int):
        """Call the OpenAI client using the available API surface."""

        client = self.client
        if hasattr(client, "responses"):
            return client.responses.create(
                model=self.model,
                input=messages,
                max_output_tokens=max_tokens,
                temperature=self.temperature,
            )

        # Fallback for OpenAI<=2.x without the responses API
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
        parts: List[str] = []

        def _append_if_text(value: object) -> None:
            text = self._coerce_text(value)
            if text:
                parts.append(text)

        # OpenAI v1.55+ "responses" API
        if hasattr(response, "model_dump"):
            try:
                dumped = response.model_dump()  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive
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
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return "".join(ch for ch in str(value) if ch.isprintable())
