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
from app.backend.gemini_client import GeminiClient

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
        label="Pour un achat",
        message_type_id="remercier",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Remercier clairement pour l'achat.",
            "Mentionner la préparation rapide et l'envoi du suivi.",
            "Glisser une invitation légère à visiter le dressing.",
            "Ton chaleureux et concis en une seule phrase.",
        ),
        allowed_articles=None,
    ),
    "remercier_acceptation_offre": ScenarioConfig(
        id="remercier_acceptation_offre",
        label="Après avoir accepté une offre",
        message_type_id="remercier",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Confirmer l'acceptation de l'offre et remercier chaleureusement.",
            "Indiquer explicitement : je prépare la commande dès que le paiement est validé par Vinted.",
            "Rester bref (1 phrase), positif et inviter à suivre l'envoi.",
        ),
        allowed_articles=None,
    ),
    "remercier_avis": ScenarioConfig(
        id="remercier_avis",
        label="Pour une évaluation",
        message_type_id="remercier",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Remercier pour l'avis laissé.",
            "Souligner que le feedback aide à améliorer le service.",
            "Rester bref et positif en une phrase.",
        ),
        allowed_articles=None,
    ),
    "remercier_favori": ScenarioConfig(
        id="remercier_favori",
        label="Pour l'ajout d'un favoris",
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
        label="À l'achat",
        message_type_id="inciter",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Mettre en avant la disponibilité actuelle et l'envoi rapide.",
            "Créer un léger sentiment d'urgence sans être agressif.",
            "Conclure par une invitation à passer commande et à regarder le dressing.",
            "Formuler l'ensemble en une seule phrase simple et positive.",
        ),
        allowed_articles=None,
    ),
    "inciter_lot": ScenarioConfig(
        id="inciter_lot",
        label="À constituer un lot",
        message_type_id="inciter",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Proposer de regrouper plusieurs articles pour un envoi unique.",
            "Suggérer un avantage tarifaire ou frais de port optimisé.",
            "Ton convivial et orienté solution, en invitant à explorer le dressing.",
            "Tout dire en une seule phrase directe et positive.",
        ),
        allowed_articles=None,
    ),
    "negocier_plus_haut": ScenarioConfig(
        id="negocier_plus_haut",
        label="Un prix plus haut",
        message_type_id="negocier",
        requires_client_message=False,
        extra_fields=["contre_offre"],
        rules=(
            "Remercier pour l'intérêt ou l'offre.",
            "Expliquer que la proposition est trop basse au regard de la qualité.",
            "Proposer un montant révisé (contre-offre) clair et valoriser l'article.",
            "Utiliser exactement la contre-offre fournie (montant inchangé).",
            "Mentionner l'envoi rapide et encourager à valider ou regarder le dressing.",
            "Utiliser uniquement l'une des deux phrases courtes prévues pour cette situation (pas d'autres variations).",
        ),
        allowed_articles=None,
        examples=(
            "Merci pour votre offre, j’envoie dès demain 🚀",
            "Merci pour votre offre, l'article est en très bon état pour {contre_offre}€ c’est bon pour moi et j’envoie dès demain matin ;)",
        ),
    ),
    "negocier_reservation": ScenarioConfig(
        id="negocier_reservation",
        label="Une demande de réservation",
        message_type_id="negocier",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Remercier pour l'intérêt et la demande de réservation.",
            "Expliquer simplement que la plateforme fonctionne sans réservation à l'avance (ex: \"Les articles restent disponibles en continu, vous pouvez valider quand vous êtes prête.\").",
            "Proposer une alternative (achat direct, lot ou délai court) sans mentionner de prix.",
            "Ton courtois, ferme mais encourageant, en invitant à valider rapidement.",
            "Répondre en une seule phrase positive sans négation.",
        ),
        allowed_articles=None,
        examples=(
            dedent(
                """
                Bonjour, merci pour votre message, la plateforme fonctionne sans réservation à l'avance et vous pouvez valider dès maintenant si le jean vous plaît.
                """
            ).strip(),
        ),
    ),
    "negocier_prix_ferme": ScenarioConfig(
        id="negocier_prix_ferme",
        label="Un prix ferme",
        message_type_id="negocier",
        requires_client_message=False,
        extra_fields=["offre_client", "prix_ferme"],
        rules=(
            "Remercier pour l'intérêt.",
            "Dire simplement que vous restez sur le prix indiqué sans employer l'expression 'prix ferme'.",
            "Reprendre exactement le prix saisi (sans le modifier).",
            "Rester courtois, concis et orienté sur l'envoi rapide si la vente est validée.",
            "Tout tenir en une phrase positive et directe.",
        ),
        allowed_articles=None,
    ),
    "informer_preparation": ScenarioConfig(
        id="informer_preparation",
        label="De la préparation du colis",
        message_type_id="informer",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Confirmer la validation du paiement et la préparation en cours.",
            "Partager le délai ou la promesse d'envoi.",
            "Ton rassurant en une phrase avec un clin d'œil convivial.",
        ),
        allowed_articles=None,
    ),
    "informer_envoi": ScenarioConfig(
        id="informer_envoi",
        label="De l'envois du colis",
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
    "informer_envoi_aujourdhui": ScenarioConfig(
        id="informer_envoi_aujourdhui",
        label="D'un envoi aujourd'hui",
        message_type_id="informer",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Informer clairement que le colis part aujourd'hui (formule explicite).",
            "Préciser le dépôt imminent ou en cours et que Vinted mettra à jour le suivi dès le premier scan.",
            "Rester très concis (1 phrase), sans formules pompeuses, et rassurer sur la prise en charge rapide.",
        ),
        allowed_articles=None,
    ),
    "informer_livraison": ScenarioConfig(
        id="informer_livraison",
        label="De la livraison du colis",
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
    "informer_retour": ScenarioConfig(
        id="informer_retour",
        label="De l'acceptation d'un retour",
        message_type_id="informer",
        requires_client_message=False,
        extra_fields=[],
        rules=(
            "Confirmer que le retour a été accepté et que les instructions de renvoi sont valides.",
            "Préciser le délai ou l'étape suivante pour le remboursement ou l'échange.",
            "Rester rassurant en une phrase et inviter à revenir vers vous en cas de question.",
        ),
        allowed_articles=None,
    ),
}

STYLE_RULES: Sequence[str] = (
    "Réponds en français avec un ton simple, cordial et convivial.",
    "Utiliser un vocabulaire courant, sans superlatifs ni tournures pompeuses.",
    "Pas de chichi : éviter les formules creuses ou vendeuses (ex. \"parfait pour la saison\").",
    "Inclure au maximum un seul émoji ou smiley.",
    "Rédiger une seule phrase courte, sans puces ni listes.",
    "Ne rien promettre d'irréaliste ; tu peux mentionner un envoi rapide si pertinent.",
    "Tutoiement interdit : vouvoie toujours le client et parles en ton nom (\"je\").",
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
        provider: str = "openai",
        temperature: float = 0.3,
    ) -> None:
        self.model = model or os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.provider = provider
        if not 0 <= temperature <= 1:
            raise ValueError("La température doit être comprise entre 0 et 1")
        self.temperature = temperature
        self._client: Optional[OpenAI] = None
        self._gemini_client: Optional[GeminiClient] = None
        logger.step(
            "CustomerReplyGenerator initialisé avec le modèle %s/%s et une température de %.2f",
            self.provider,
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
                            "Tu es un vendeur Vinted (Durin31). Tu réponds en français avec un ton simple, "
                            "cordial et convivial. Tu vouvoies toujours le client (jamais de tutoiement) et "
                            "parles en ton nom (je). Utilise une seule phrase courte avec un vocabulaire "
                            "courant, sans tournures pompeuses ni superlatifs de qualité. Ta réponse doit contenir "
                            "au maximum un émoji, éviter les puces ou numéros, et rester orientée client. Formule "
                            "sans négations (pas de 'pas', 'jamais', 'malheureusement') et ne promets rien que tu "
                            "ne puisses tenir."
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
        article_label = self._resolve_article_label(
            article_type=payload.article_type, scenario=scenario
        )
        context_lines = [
            f"Client: {payload.client_name}",
            f"Scénario: {scenario.label}",
            f"Article: {article_label}",
        ]
        if payload.client_message:
            context_lines.append(f"Message client: {payload.client_message.strip()}")

        price_details = []
        include_client_offer = scenario.id != "negocier_plus_haut"
        if include_client_offer and payload.offre_client is not None:
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

    def _resolve_article_label(
        self, *, article_type: str, scenario: ScenarioConfig
    ) -> str:
        base_label = get_article_label(article_type)
        if article_type != "autre":
            return base_label

        order_related_scenarios = {
            "remercier_achat",
            "remercier_acceptation_offre",
            "informer_preparation",
            "informer_envoi",
            "informer_envoi_aujourdhui",
            "informer_livraison",
            "informer_retour",
        }

        if scenario.id in order_related_scenarios or scenario.message_type_id == "informer":
            return "Votre commande"

        return "Votre article"

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

        if has_price_details and scenario.message_type_id == "negocier":
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

        if scenario.message_type_id in {"informer", "inciter"}:
            rules.append(
                "Formuler le message en une seule phrase percutante sans ajouter de justification tarifaire."
            )

        return rules

    def _create_response(self, messages: Sequence[dict], *, max_tokens: int):
        """Appelle le fournisseur approprié (OpenAI ou Gemini)."""

        if self.provider == "gemini":
            client = self._gemini_client or GeminiClient(self.model, self.api_key or "")
            self._gemini_client = client
            return client.generate(
                messages, max_tokens=max_tokens, temperature=self.temperature
            )

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

        if isinstance(response, str):
            return response.strip()

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
