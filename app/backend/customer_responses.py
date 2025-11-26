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
class MessageType:
    id: str
    label: str


@dataclass(frozen=True)
class ScenarioConfig:
    id: str
    label: str
    message_type_id: str
    requires_client_message: bool
    extra_fields: Sequence[str]
    rules: Sequence[str]
    allowed_articles: Optional[Sequence[str]] = None
    examples: Sequence[str] = ()


@dataclass
class CustomerReplyPayload:
    client_name: str
    article_type: str
    scenario_id: str
    client_message: str = ""
    offre_client: Optional[float] = None
    contre_offre: Optional[float] = None
    prix_ferme: Optional[float] = None


ARTICLE_TYPES: Sequence[ArticleType] = (
    ArticleType("jean_levis", "Jean Levi's"),
    ArticleType("pull_tommy", "Pull Tommy Hilfiger"),
    ArticleType("jacket", "Jacket / Veste"),
    ArticleType("polaire_tnf", "Polaire The North Face"),
    ArticleType("polaire_columbia", "Polaire Columbia"),
    ArticleType("autre", "Autre article"),
)


EXTRA_FIELD_LABELS: Dict[str, str] = {
    "offre_client": "Offre du client",
    "contre_offre": "Votre proposition",
    "prix_ferme": "Prix ferme",
}


MESSAGE_TYPES: Sequence[MessageType] = (
    MessageType("remercier", "Remercier"),
    MessageType("inciter", "Inciter"),
    MessageType("negocier", "Négocier"),
    MessageType("informer", "Informer"),
)

MESSAGE_TYPE_EXTRA_FIELDS: Dict[str, Sequence[str]] = {}


SCENARIOS: Dict[str, ScenarioConfig] = {
    "remercier_achat": ScenarioConfig(
        id="remercier_achat",
        label="Remercier pour un achat",
        message_type_id="remercier",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Remercier clairement pour l'achat.",
            "Mentionner la préparation rapide et l'envoi du suivi.",
            "Glisser une invitation légère à visiter le dressing.",
            "Ton chaleureux mais concis (2–3 phrases).",
        ),
        allowed_articles=None,
    ),
    "remercier_avis": ScenarioConfig(
        id="remercier_avis",
        label="Remercier pour un avis",
        message_type_id="remercier",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Remercier pour l'avis laissé.",
            "Souligner que le feedback aide à améliorer le service.",
            "Rester bref et positif (1–2 phrases).",
        ),
        allowed_articles=None,
    ),
    "remercier_favori": ScenarioConfig(
        id="remercier_favori",
        label="Remercier pour l'ajout en favori",
        message_type_id="remercier",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Remercier pour l'ajout en favori.",
            "Mentionner que l'article est disponible pour le moment.",
            "Inviter discrètement à finaliser ou poser une question.",
        ),
        allowed_articles=None,
    ),
    "inciter_achat": ScenarioConfig(
        id="inciter_achat",
        label="Inciter à l'achat",
        message_type_id="inciter",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Mettre en avant la disponibilité actuelle et l'envoi rapide.",
            "Créer un léger sentiment d'urgence sans être agressif.",
            "Conclure par une invitation à passer commande et à regarder le dressing.",
        ),
        allowed_articles=None,
    ),
    "inciter_lot": ScenarioConfig(
        id="inciter_lot",
        label="Inciter à faire un lot",
        message_type_id="inciter",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Proposer de regrouper plusieurs articles pour un envoi unique.",
            "Suggérer un avantage tarifaire ou frais de port optimisé.",
            "Ton convivial et orienté solution, en invitant à explorer le dressing.",
        ),
        allowed_articles=None,
    ),
    "negocier_plus_haut": ScenarioConfig(
        id="negocier_plus_haut",
        label="Négocier un prix plus haut",
        message_type_id="negocier",
        requires_client_message=False,
        extra_fields=["offre_client", "contre_offre"],
        rules=(
            "Remercier pour l'intérêt ou l'offre.",
            "Expliquer que la proposition est trop basse au regard de la qualité.",
            "Proposer un montant révisé (contre-offre) clair et valoriser l'article.",
            "Utiliser exactement la contre-offre fournie (montant inchangé).",
            "Mentionner l'envoi rapide et encourager à valider ou regarder le dressing.",
        ),
        allowed_articles=None,
    ),
    "negocier_reservation": ScenarioConfig(
        id="negocier_reservation",
        label="Négocier une demande de réservation",
        message_type_id="negocier",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Remercier pour l'intérêt et la demande de réservation.",
            "Expliquer que la plateforme ne permet pas de réserver en amont (ex: \"Malheureusement Vinted ne permet pas de réserver ces produits à l'avance.\").",
            "Proposer une alternative (achat direct, lot ou délai court) sans mentionner de prix.",
            "Ton courtois, ferme mais encourageant, en invitant à valider rapidement.",
        ),
        allowed_articles=None,
        examples=(
            dedent(
                """
                Bonjour,
                Merci pour votre message ! Malheureusement Vinted ne permet pas de réserver ces produits à l'avance, mais vous pouvez le valider dès maintenant.
                Si malgré tout ce jean vous intéresse et qu'il est toujours disponible jeudi, il sera toujours là pour vous.
                """
            ).strip(),
        ),
    ),
    "negocier_prix_ferme": ScenarioConfig(
        id="negocier_prix_ferme",
        label="Prix ferme (pas de négociation)",
        message_type_id="negocier",
        requires_client_message=False,
        extra_fields=["offre_client", "prix_ferme"],
        rules=(
            "Remercier pour l'intérêt.",
            "Indiquer que le prix est ferme en justifiant brièvement (état, modèle).",
            "Reprendre exactement le prix ferme saisi (sans le modifier).",
            "Rester courtois et concis, en rappelant l'envoi rapide et le dressing.",
        ),
        allowed_articles=None,
    ),
    "informer_preparation": ScenarioConfig(
        id="informer_preparation",
        label="Préparation du colis (paiement validé)",
        message_type_id="informer",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Confirmer la validation du paiement et la préparation en cours.",
            "Partager le délai ou la promesse d'envoi.",
            "Ton rassurant, 2 phrases max, avec un clin d'œil convivial.",
        ),
        allowed_articles=None,
    ),
    "informer_envoi": ScenarioConfig(
        id="informer_envoi",
        label="Envoi du colis",
        message_type_id="informer",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Indiquer que le colis vient d'être déposé ou scanné.",
            "Préciser que le suivi est partagé/à jour.",
            "Rester bref et pro, en gardant un ton chaleureux.",
        ),
        allowed_articles=None,
    ),
    "informer_livraison": ScenarioConfig(
        id="informer_livraison",
        label="Livraison du colis",
        message_type_id="informer",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Informer que le colis est indiqué livré ou disponible en point relais.",
            "Inviter à confirmer la bonne réception ou à signaler un souci.",
            "Proposer de laisser un avis si tout est conforme.",
        ),
        allowed_articles=None,
    ),
}

STYLE_RULES: Sequence[str] = (
    "Réponds en français avec un ton courtois, professionnel, fun, avenant et convivial.",
    "Inclure au moins deux émojis ou smileys répartis dans la réponse.",
    "Rédiger entre 1 et 4 phrases maximum, sans puces ni listes.",
    "Ne rien promettre d'irréaliste ; tu peux mentionner un envoi rapide si pertinent.",
)


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
        temperature: float = 0.5,
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
                            "Tu es un vendeur professionnel Vinted (Durin31). Tu réponds en français avec "
                            "un ton courtois, professionnel, fun, avenant et convivial. Ta réponse doit "
                            "contenir au moins deux émojis, rester concise (1 à 4 phrases), sans puces ni "
                            "numéros, et orientée client. Tu ne promets rien que tu ne puisses tenir."
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
        context_lines = [
            f"Client: {payload.client_name}",
            f"Scénario: {scenario.label}",
            f"Article: {article_label}",
        ]
        if payload.client_message:
            context_lines.append(f"Message client: {payload.client_message.strip()}")

        price_details = []
        if payload.offre_client is not None:
            price_details.append(f"Offre client: {payload.offre_client}€")
        if payload.contre_offre is not None:
            price_details.append(f"Votre proposition: {payload.contre_offre}€")
        if payload.prix_ferme is not None:
            price_details.append(f"Prix ferme: {payload.prix_ferme}€")
        if price_details:
            context_lines.append(" / ".join(price_details))

        rules = list(scenario.rules)
        rules.extend(
            self._build_personalization_rules(
                payload=payload,
                scenario=scenario,
                article_label=article_label,
                has_price_details=bool(price_details),
            )
        )
        rules.extend(STYLE_RULES)

        examples_block = ""
        if scenario.examples:
            examples_block = "\n\nExemples de réponse:\n- " + "\n- ".join(scenario.examples)

        prompt = dedent(
            """
            Contexte client et article:
            {context}

            Règles spécifiques:
            - {rules}

            {examples}

            Rédige la réponse finale en suivant le ton Durin31.
            """
        ).format(
            context="\n".join(context_lines),
            rules="\n- ".join(rules),
            examples=examples_block.strip(),
        )

        logger.info("Prompt de réponse client construit (%d caractères)", len(prompt))
        return prompt.strip()

    def _build_personalization_rules(
        self,
        *,
        payload: CustomerReplyPayload,
        scenario: ScenarioConfig,
        article_label: str,
        has_price_details: bool,
    ) -> Sequence[str]:
        """Add anti-redondancy cues so replies feel fresher and more contextual."""

        rules = [
            "Varier l'accroche et la conclusion pour éviter les formules toutes faites.",
            f"Citer l'article ({article_label}) pour ancrer la réponse et éviter les messages génériques.",
            "Ne pas répéter deux fois la même formule (remerciements ou invitation) dans le message.",
            "Ajouter un mini détail concret (état général, style ou saison) sans inventer de faits précis.",
        ]

        if has_price_details:
            rules.append(
                "Expliquer en une phrase pourquoi le prix proposé est cohérent (qualité, état, demande)."
            )

        if payload.client_message.strip():
            rules.append(
                "Réagir brièvement au message du client pour montrer que sa demande a été comprise."
            )

        if scenario.message_type_id == "negocier":
            rules.append(
                "Utiliser des tournures variées (pas toujours 'merci pour l'offre') pour dynamiser la négociation."
            )

        return rules

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
