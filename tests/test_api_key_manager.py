from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend import api_key_manager


@pytest.fixture(autouse=True)
def reload_module():
    """Ensure environment-driven helpers are recalculated for each test."""

    yield
    importlib.reload(api_key_manager)


def test_config_dir_prefers_appdata(monkeypatch, tmp_path):
    monkeypatch.setattr(api_key_manager, "_is_windows", lambda: True)
    appdata = tmp_path / "Roaming"
    appdata.mkdir()
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    config_dir, config_file = api_key_manager._config_paths()
    assert config_dir == appdata / "VintedAssistant"
    assert config_file == config_dir / "openai_api_key"


def test_config_dir_falls_back_to_localappdata(monkeypatch, tmp_path):
    monkeypatch.setattr(api_key_manager, "_is_windows", lambda: True)
    monkeypatch.delenv("APPDATA", raising=False)
    local_appdata = tmp_path / "Local"
    local_appdata.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))

    config_dir, _config_file = api_key_manager._config_paths()
    assert config_dir == local_appdata / "VintedAssistant"


def test_config_dir_home_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(api_key_manager, "_is_windows", lambda: True)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    config_dir, config_file = api_key_manager._config_paths()
    expected_dir = tmp_path / "AppData" / "Roaming" / "VintedAssistant"
    assert config_dir == expected_dir
    assert config_file == expected_dir / "openai_api_key"


def test_config_dir_posix(monkeypatch, tmp_path):
    monkeypatch.setattr(api_key_manager, "_is_windows", lambda: False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    config_dir, config_file = api_key_manager._config_paths()
    expected_dir = tmp_path / ".vinted_assistant"
    assert config_dir == expected_dir
    assert config_file == expected_dir / "openai_api_key"


def test_save_api_key_uses_windows_location(monkeypatch, tmp_path):
    monkeypatch.setattr(api_key_manager, "_is_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(api_key_manager, "_write_to_keyring", lambda api_key: False)

    api_key_manager.save_api_key("test-key")

    config_dir, config_file = api_key_manager._config_paths()
    assert config_dir == tmp_path / "VintedAssistant"
    assert config_file.read_text(encoding="utf-8") == "test-key"
    assert api_key_manager.os.environ["OPENAI_API_KEY"] == "test-key"

