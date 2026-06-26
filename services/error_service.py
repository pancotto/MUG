"""Centralized exception logging and user-message formatting."""

from __future__ import annotations

from infrastructure.logging_config import get_logger


class ErrorService:
    def __init__(self):
        self._logger = get_logger(__name__)

    def log_exception(self, exc: BaseException, context: str = "") -> None:
        message = context or "Unhandled application exception"
        self._logger.exception("%s: %s", message, exc)

    def format_user_message(self, title: str, details: str | BaseException) -> str:
        detail_text = str(details).strip()
        if not detail_text:
            return title
        return f"{title}\n\n{detail_text}"

