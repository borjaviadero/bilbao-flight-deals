"""Tests for the Telegram notifier (no network: the transport is faked)."""

from __future__ import annotations

import json
import urllib.request

import pytest

from dealhunter_core.config import ResolvedTelegramTarget
from dealhunter_core.http import HttpResponse, JsonHttpClient
from dealhunter_core.telegram import TelegramError, TelegramNotifier

TOKEN = "123456:SECRET-token"
TARGET = ResolvedTelegramTarget(chat_id=-1001, topic_id=2)


def notifier(*responses: HttpResponse) -> tuple[TelegramNotifier, list[urllib.request.Request]]:
    queue = list(responses)
    seen: list[urllib.request.Request] = []

    def transport(request: urllib.request.Request, timeout: float) -> HttpResponse:
        seen.append(request)
        return queue.pop(0)

    http = JsonHttpClient(transport=transport, retries=0, sleep=lambda _: None)
    return TelegramNotifier(TOKEN, TARGET, http), seen


def test_send_posts_to_the_topic() -> None:
    bot, seen = notifier(HttpResponse(200, b'{"ok": true, "result": {}}'))
    bot.send("<b>hello</b>")
    request = seen[0]
    assert request.full_url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = json.loads(request.data)  # type: ignore[arg-type]
    assert payload == {
        "chat_id": -1001,
        "message_thread_id": 2,
        "text": "<b>hello</b>",
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }


def test_http_errors_never_show_the_token() -> None:
    bot, _ = notifier(HttpResponse(401, b'{"ok": false}'))
    with pytest.raises(TelegramError) as info:
        bot.send("x")
    assert TOKEN not in str(info.value)
    assert "<bot-token>" in str(info.value)
    assert info.value.__cause__ is None


def test_rejected_message() -> None:
    bot, _ = notifier(HttpResponse(200, b'{"ok": false, "description": "Bad Request"}'))
    with pytest.raises(TelegramError, match="Bad Request"):
        bot.send("x")


def test_too_long() -> None:
    bot, seen = notifier()
    with pytest.raises(TelegramError, match="too long"):
        bot.send("x" * 5000)
    assert seen == []


def test_http_error_includes_telegram_reason() -> None:
    body = b'{"ok": false, "error_code": 400, "description": "Bad Request: chat not found"}'
    bot, _ = notifier(HttpResponse(400, body))
    with pytest.raises(TelegramError, match="HTTP 400: Bad Request: chat not found"):
        bot.send("x")
