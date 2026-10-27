"""Send messages to a Telegram group topic through the Bot API.

The Bot API puts the bot token in the URL path, so any error raised here is
re-created with the token redacted and without the original exception chained.
"""

from __future__ import annotations

from typing import Any

from dealhunter_core.config import ResolvedTelegramTarget
from dealhunter_core.http import HttpError, JsonHttpClient

API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096  # Telegram limit, in characters


class TelegramError(Exception):
    """A message could not be delivered."""


class TelegramNotifier:
    """Posts HTML-formatted messages to one chat topic."""

    def __init__(self, token: str, target: ResolvedTelegramTarget, http: JsonHttpClient) -> None:
        self._token = token
        self._target = target
        self._http = http

    def send(self, text: str) -> None:
        """Send one message (HTML parse mode, link previews disabled)."""
        if len(text) > MAX_MESSAGE_LENGTH:
            raise TelegramError(f"message too long ({len(text)} > {MAX_MESSAGE_LENGTH} chars)")
        payload: dict[str, Any] = {
            "chat_id": self._target.chat_id,
            "message_thread_id": self._target.topic_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        try:
            response = self._http.post_json(f"{API_BASE}/bot{self._token}/sendMessage", payload)
        except HttpError as exc:
            raise TelegramError(self._redact(str(exc))) from None

        if not isinstance(response, dict) or response.get("ok") is not True:
            description = response.get("description") if isinstance(response, dict) else response
            raise TelegramError(f"Telegram rejected the message: {self._redact(str(description))}")

    def _redact(self, text: str) -> str:
        return text.replace(self._token, "<bot-token>")
