"""Tests for the JSON HTTP client (no network: the transport is faked)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from dealhunter_core.http import HttpError, HttpResponse, JsonHttpClient


class FakeTransport:
    """Returns queued responses (or raises queued exceptions) and records requests."""

    def __init__(self, *responses: HttpResponse | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> HttpResponse:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def ok(payload: object) -> HttpResponse:
    return HttpResponse(200, json.dumps(payload).encode())


def client(transport: FakeTransport, sleeps: list[float]) -> JsonHttpClient:
    return JsonHttpClient(transport=transport, retries=2, backoff=1.0, sleep=sleeps.append)


def test_get_json_sends_params_and_headers() -> None:
    transport, sleeps = FakeTransport(ok({"a": 1})), []
    result = client(transport, sleeps).get_json(
        "https://api.test/x", params={"q": "BIO", "n": 2}, headers={"X-Token": "secret"}
    )
    assert result == {"a": 1}
    request = transport.requests[0]
    assert request.full_url == "https://api.test/x?q=BIO&n=2"
    assert request.get_header("X-token") == "secret"
    assert request.get_method() == "GET"
    assert sleeps == []


def test_post_json_sends_body() -> None:
    transport, sleeps = FakeTransport(ok({"ok": True})), []
    client(transport, sleeps).post_json("https://api.test/send", {"text": "hi"})
    request = transport.requests[0]
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"text": "hi"}  # type: ignore[arg-type]
    assert request.get_header("Content-type") == "application/json"


def test_retries_server_errors_with_backoff() -> None:
    transport = FakeTransport(HttpResponse(503, b""), HttpResponse(502, b""), ok([1]))
    sleeps: list[float] = []
    assert client(transport, sleeps).get_json("https://api.test/x") == [1]
    assert sleeps == [1.0, 2.0]


def test_respects_retry_after_with_a_cap() -> None:
    transport = FakeTransport(
        HttpResponse(429, b"", {"Retry-After": "5"}),
        HttpResponse(429, b"", {"Retry-After": "999"}),
        ok({}),
    )
    sleeps: list[float] = []
    client(transport, sleeps).get_json("https://api.test/x")
    assert sleeps == [5.0, 60.0]


def test_retries_network_errors() -> None:
    transport = FakeTransport(urllib.error.URLError("down"), ok({"back": True}))
    sleeps: list[float] = []
    assert client(transport, sleeps).get_json("https://api.test/x") == {"back": True}
    assert len(sleeps) == 1


def test_gives_up_after_retries() -> None:
    transport = FakeTransport(*[HttpResponse(503, b"")] * 3)
    with pytest.raises(HttpError) as info:
        client(transport, []).get_json("https://api.test/x")
    assert info.value.status == 503
    assert len(transport.requests) == 3


def test_client_errors_are_not_retried_and_hide_query() -> None:
    transport = FakeTransport(HttpResponse(401, b""))
    with pytest.raises(HttpError, match="HTTP 401") as info:
        client(transport, []).get_json("https://api.test/x", params={"token": "secret"})
    assert "secret" not in str(info.value)
    assert len(transport.requests) == 1


def test_invalid_json() -> None:
    transport = FakeTransport(HttpResponse(200, b"<html>"))
    with pytest.raises(HttpError, match="invalid JSON"):
        client(transport, []).get_json("https://api.test/x")


def test_http_error_keeps_the_body() -> None:
    client = JsonHttpClient(
        transport=lambda request, timeout: HttpResponse(400, b'{"why": "bad"}'),
        retries=0,
        sleep=lambda _: None,
    )
    with pytest.raises(HttpError) as info:
        client.get_json("https://example.test/x?token=secret")
    assert info.value.status == 400
    assert info.value.body == b'{"why": "bad"}'
    assert "secret" not in str(info.value)
