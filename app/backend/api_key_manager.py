"""Helpers to manage the OpenAI API key for the desktop application."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from app.logger import get_logger

try:  # pragma: no cover - optional dependency
    import keyring  # type: ignore
except Exception:  # pragma: no cover - keyring may be unavailable
    keyring = None  # type: ignore


logger = get_logger(__name__)

_SERVICE_NAME = "VintedListingAssistant"
_ACCOUNT_NAME = "openai_api_key"
_CONFIG_DIR = Path.home() / ".vinted_assistant"
_CONFIG_FILE = _CONFIG_DIR / "openai_api_key"


def _read_from_keyring() -> Optional[str]:
    if keyring is None:  # pragma: no cover - depends on optional dependency
        logger.info("Module keyring indisponible, passage au stockage fichier")
        return None
    try:
        value = keyring.get_password(_SERVICE_NAME, _ACCOUNT_NAME)
        if value:
            logger.success("Clé API récupérée depuis le trousseau système")
        return value or None
    except Exception:  # pragma: no cover - platform specific errors
        logger.exception("Impossible d'accéder au trousseau système")
        return None


def _read_from_file() -> Optional[str]:
    if not _CONFIG_FILE.exists():
        logger.info("Fichier de configuration absent (%s)", _CONFIG_FILE)
        return None
    try:
        value = _CONFIG_FILE.read_text(encoding="utf-8").strip()
        if value:
            logger.success("Clé API chargée depuis le fichier sécurisé")
        return value or None
    except OSError:
        logger.exception("Lecture du fichier de configuration impossible")
        return None


def _write_to_keyring(api_key: str) -> bool:
    if keyring is None:  # pragma: no cover - depends on optional dependency
        return False
    try:
        keyring.set_password(_SERVICE_NAME, _ACCOUNT_NAME, api_key)
    except Exception:  # pragma: no cover - platform specific errors
        logger.exception("Échec de l'enregistrement dans le trousseau système")
        return False
    logger.success("Clé API enregistrée dans le trousseau système")
    return True


def _write_to_file(api_key: str) -> bool:
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _CONFIG_FILE.write_text(api_key, encoding="utf-8")
        try:
            _CONFIG_FILE.chmod(0o600)  # Meilleur effort, peut échouer sous Windows
        except OSError:  # pragma: no cover - dépend du système
            logger.warning("Impossible de restreindre les permissions du fichier")
    except OSError:
        logger.exception("Échec de l'écriture du fichier de configuration")
        return False
    logger.success("Clé API sauvegardée dans le fichier sécurisé")
    return True


def save_api_key(api_key: str) -> None:
    """Persist the provided API key securely and expose it as an environment variable."""

    clean_key = api_key.strip()
    if not clean_key:
        raise ValueError("La clé API ne peut pas être vide")

    if not _write_to_keyring(clean_key):
        logger.info("Utilisation du stockage fichier pour la clé API")
        if not _write_to_file(clean_key):
            raise RuntimeError("Impossible de sauvegarder la clé API")

    os.environ["OPENAI_API_KEY"] = clean_key
    logger.success("Variable d'environnement OPENAI_API_KEY définie")


def get_api_key() -> Optional[str]:
    """Return the OpenAI API key if it is available."""

    env_value = os.getenv("OPENAI_API_KEY")
    if env_value and env_value.strip():
        logger.info("Clé API récupérée depuis l'environnement")
        return env_value.strip()

    for loader in (_read_from_keyring, _read_from_file):
        value = loader()
        if value:
            os.environ["OPENAI_API_KEY"] = value
            return value

    return None


def ensure_api_key(master) -> str:
    """Ensure an API key is available, prompting the user if necessary."""

    api_key = get_api_key()
    if api_key:
        return api_key

    from app.ui.api_key_dialog import APIKeyDialog  # Import tardif pour éviter une boucle

    dialog = APIKeyDialog(master)
    master.wait_window(dialog)

    api_key = get_api_key()
    if not api_key:
        logger.error("Aucune clé API fournie par l'utilisateur")
        raise RuntimeError("Clé API OpenAI requise pour poursuivre")
    return api_key
