from __future__ import annotations

"""Gestion des modèles API configurables pour l'application bureau."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from app.backend.api_key_manager import get_api_key
from app.logger import get_logger

logger = get_logger(__name__)

_CONFIG_DIR = Path.home() / ".vinted_assistant"
_MODEL_FILE = _CONFIG_DIR / "models.json"
_DEFAULT_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class ModelEntry:
    """Modèle et clé API associés."""

    name: str
    api_key: str


@dataclass(frozen=True)
class ModelSettings:
    """Collection des modèles disponibles et du modèle actif."""

    current_model: str
    models: Dict[str, ModelEntry]

    @property
    def current_entry(self) -> ModelEntry:
        if self.current_model not in self.models:
            raise KeyError(f"Modèle actif introuvable: {self.current_model}")
        return self.models[self.current_model]


def _serialize(settings: ModelSettings) -> dict:
    return {
        "current_model": settings.current_model,
        "models": {name: {"name": entry.name, "api_key": entry.api_key} for name, entry in settings.models.items()},
    }


def _deserialize(data: dict, *, fallback_model: str, fallback_key: str) -> ModelSettings:
    models: Dict[str, ModelEntry] = {}
    for name, raw in data.get("models", {}).items():
        api_key = str(raw.get("api_key", "")).strip()
        if not name or not api_key:
            continue
        models[name] = ModelEntry(name=name, api_key=api_key)

    if not models:
        models[fallback_model] = ModelEntry(name=fallback_model, api_key=fallback_key)

    current_model = data.get("current_model") or fallback_model
    if current_model not in models:
        current_model = fallback_model

    return ModelSettings(current_model=current_model, models=models)


def load_model_settings() -> ModelSettings:
    """Charge les modèles connus, en créant un fichier par défaut si nécessaire."""

    default_model = os.getenv("OPENAI_TEXT_MODEL", _DEFAULT_MODEL)
    default_key = get_api_key() or ""

    if not _MODEL_FILE.exists():
        logger.info("Aucun fichier de modèles détecté, création d'une configuration par défaut")
        settings = ModelSettings(
            current_model=default_model,
            models={default_model: ModelEntry(name=default_model, api_key=default_key)},
        )
        save_model_settings(settings)
        return settings

    try:
        data = json.loads(_MODEL_FILE.read_text(encoding="utf-8"))
        settings = _deserialize(data, fallback_model=default_model, fallback_key=default_key)
    except (OSError, json.JSONDecodeError):
        logger.exception("Échec de lecture du fichier de modèles, réinitialisation")
        settings = ModelSettings(
            current_model=default_model,
            models={default_model: ModelEntry(name=default_model, api_key=default_key)},
        )
        save_model_settings(settings)
        return settings

    if default_model not in settings.models:
        settings = ModelSettings(
            current_model=settings.current_model,
            models={**settings.models, default_model: ModelEntry(name=default_model, api_key=default_key)},
        )
        save_model_settings(settings)

    return settings


def save_model_settings(settings: ModelSettings) -> None:
    """Enregistre la configuration des modèles sur le disque."""

    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _MODEL_FILE.write_text(json.dumps(_serialize(settings), indent=2), encoding="utf-8")
        logger.success("Configuration des modèles sauvegardée (%s)", settings.current_model)
    except OSError:
        logger.exception("Impossible de sauvegarder les modèles configurés")
        raise


def add_model(settings: ModelSettings, *, name: str, api_key: str) -> ModelSettings:
    """Ajoute un nouveau modèle et le définit comme actif."""

    clean_name = name.strip()
    clean_key = api_key.strip()
    if not clean_name:
        raise ValueError("Le nom du modèle est obligatoire")
    if not clean_key:
        raise ValueError("La clé API du modèle est obligatoire")

    models = dict(settings.models)
    models[clean_name] = ModelEntry(name=clean_name, api_key=clean_key)
    return ModelSettings(current_model=clean_name, models=models)


def apply_current_model(settings: ModelSettings) -> None:
    """Expose le modèle actif via les variables d'environnement."""

    entry = settings.current_entry
    os.environ["OPENAI_API_KEY"] = entry.api_key
    os.environ["OPENAI_TEXT_MODEL"] = entry.name
    os.environ["OPENAI_VISION_MODEL"] = entry.name
    logger.step("Modèle actif appliqué (%s)", entry.name)


def mask_api_key(api_key: str) -> str:
    """Masque une clé API en laissant seulement le préfixe et les deux derniers caractères."""

    if not api_key:
        return "Aucune clé configurée"

    visible_prefix = "sk-"
    suffix = api_key[-2:] if len(api_key) >= 2 else ""
    hidden_length = max(len(api_key) - len(visible_prefix) - len(suffix), 0)
    return f"{visible_prefix}{'*' * hidden_length}{suffix}"
