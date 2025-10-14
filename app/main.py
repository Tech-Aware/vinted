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

"""Application entry point for the Vinted listing assistant."""
from __future__ import annotations

import os
import sys
from typing import TextIO

from app.logger import get_logger
from app.ui.listing_app import VintedListingApp


logger = get_logger(__name__)


def _redirect_stream_to_null() -> TextIO | None:
    """Redirect a stream to ``os.devnull`` and return the opened descriptor."""

    try:
        return open(os.devnull, "w", encoding="utf-8")
    except OSError:
        return None


_DEVNULL_STDOUT = None
_DEVNULL_STDERR = None


def _detach_console_on_windows() -> None:
    """Detach the Windows console when the app is packaged as a GUI executable."""

    if sys.platform != "win32":
        return

    if os.environ.get("VINTED_KEEP_CONSOLE"):
        return

    try:
        import ctypes
    except Exception:  # pragma: no cover - defensive fallback on non-Windows envs
        return

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    hwnd = kernel32.GetConsoleWindow()  # type: ignore[attr-defined]
    if not hwnd:
        return

    user32.ShowWindow(hwnd, 0)  # type: ignore[attr-defined]
    kernel32.FreeConsole()  # type: ignore[attr-defined]

    global _DEVNULL_STDOUT, _DEVNULL_STDERR
    _DEVNULL_STDOUT = _redirect_stream_to_null()
    _DEVNULL_STDERR = _redirect_stream_to_null()
    if _DEVNULL_STDOUT is not None:
        sys.stdout = _DEVNULL_STDOUT
    if _DEVNULL_STDERR is not None:
        sys.stderr = _DEVNULL_STDERR


def main() -> None:
    """Start the Tkinter event loop."""

    _detach_console_on_windows()

    logger.step("Démarrage de l'application principale")
    try:
        app = VintedListingApp()
        app.mainloop()
        logger.success("Application fermée proprement")
    except Exception:
        logger.exception("Erreur critique dans la boucle principale")
        raise


if __name__ == "__main__":
    main()
