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

"""Helpers to manage the OpenAI API key for the desktop application."""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from app.logger import get_logger

try:  # pragma: no cover - optional dependency
    import keyring  # type: ignore
except Exception:  # pragma: no cover - keyring may be unavailable
    keyring = None  # type: ignore


logger = get_logger(__name__)

_SERVICE_NAME = "VintedListingAssistant"
_ACCOUNT_NAME = "openai_api_key"
_APP_DIR_NAME = "VintedAssistant"
_CONFIG_FILENAME = "openai_api_key"


def _is_windows() -> bool:
    """Return ``True`` when running on a Windows platform."""

    return sys.platform.startswith("win")


def _windows_config_dir() -> Path:
    """Return the preferred configuration directory on Windows."""

    for env_var in ("APPDATA", "LOCALAPPDATA"):
        candidate = os.getenv(env_var)
        if candidate:
            return Path(candidate) / _APP_DIR_NAME

    return Path.home() / "AppData" / "Roaming" / _APP_DIR_NAME


def _config_paths() -> Tuple[Path, Path]:
    """Return the directory and file used to store the API key."""

    if _is_windows():
        config_dir = _windows_config_dir()
    else:
        config_dir = Path.home() / ".vinted_assistant"

    return config_dir, config_dir / _CONFIG_FILENAME


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
    config_dir, config_file = _config_paths()
    if not config_file.exists():
        logger.info("Fichier de configuration absent (%s)", config_file)
        return None
    try:
        value = config_file.read_text(encoding="utf-8").strip()
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
    config_dir, config_file = _config_paths()
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file.write_text(api_key, encoding="utf-8")
        if not _is_windows():
            try:
                config_file.chmod(0o600)
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
