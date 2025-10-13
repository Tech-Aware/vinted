"""Centralized logging configuration with colored console output."""
from __future__ import annotations

import logging
import sys
from typing import Dict


# Custom log levels for workflow steps and successes.
STEP_LEVEL = 15
SUCCESS_LEVEL = 25

_CUSTOM_LEVELS_REGISTERED = False


class _ColorFormatter(logging.Formatter):
    """Formatter adding ANSI colors according to the log level."""

    _COLORS: Dict[int, str] = {
        logging.INFO: "\033[94m",  # Blue
        logging.ERROR: "\033[91m",  # Red
        logging.CRITICAL: "\033[91m",  # Red
        logging.WARNING: "\033[91m",  # Red (treated as errors for visibility)
        STEP_LEVEL: "\033[97m",  # White
        SUCCESS_LEVEL: "\033[92m",  # Green
        logging.DEBUG: "\033[97m",  # White
    }
    _RESET = "\033[0m"

    def __init__(self, fmt: str, datefmt: str | None = None, *, use_color: bool = True) -> None:
        super().__init__(fmt, datefmt)
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelno, "")
        message = super().format(record)
        if color and self._use_color:
            return f"{color}{message}{self._RESET}"
        return message


def _register_custom_levels() -> None:
    global _CUSTOM_LEVELS_REGISTERED
    if _CUSTOM_LEVELS_REGISTERED:
        return

    logging.addLevelName(STEP_LEVEL, "STEP")
    logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")

    def step(self: logging.Logger, message: str, *args, **kwargs) -> None:
        if self.isEnabledFor(STEP_LEVEL):
            self._log(STEP_LEVEL, message, args, **kwargs)

    def success(self: logging.Logger, message: str, *args, **kwargs) -> None:
        if self.isEnabledFor(SUCCESS_LEVEL):
            self._log(SUCCESS_LEVEL, message, args, **kwargs)

    logging.Logger.step = step  # type: ignore[attr-defined]
    logging.Logger.success = success  # type: ignore[attr-defined]
    _CUSTOM_LEVELS_REGISTERED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger configured with colored console output."""

    _register_custom_levels()

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream=sys.stdout)
    use_color = bool(getattr(handler.stream, "isatty", lambda: False)())
    formatter = _ColorFormatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        "%H:%M:%S",
        use_color=use_color,
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


__all__ = ["get_logger", "STEP_LEVEL", "SUCCESS_LEVEL"]

