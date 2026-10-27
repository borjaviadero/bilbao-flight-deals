"""Minimal JSON-over-HTTPS client built on the standard library.

It adds what every external call needs: a timeout, retries with backoff for
temporary failures (HTTP 429 and 5xx, network errors) and clear errors. The
transport is injectable, so tests never touch the network.

Secrets must travel in headers, never in the URL: error messages include the URL
(without its query string) but never the headers.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """What a transport returns: status code, raw body and headers."""

    status: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)


Transport = Callable[[urllib.request.Request, float], HttpResponse]


class HttpError(Exception):
    """A request failed after all retries, or returned an unusable response."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def urllib_transport(request: urllib.request.Request, timeout: float) -> HttpResponse:
    """Default transport: performs the request with :mod:`urllib`."""
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, response.read(), dict(response.headers))
    except urllib.error.HTTPError as exc:  # non-2xx responses still carry a body
        return HttpResponse(exc.code, exc.read(), dict(exc.headers or {}))


class JsonHttpClient:
    """GET/POST JSON with timeout and retries."""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        retries: int = 3,
        backoff: float = 1.0,
        user_agent: str = "bilbao-flight-deals",
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._timeout = timeout
        self._retries = retries
        self._backoff = backoff
        self._user_agent = user_agent
        self._transport = transport
        self._sleep = sleep

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """GET ``url`` with query ``params`` and return the decoded JSON body."""
        full_url = f"{url}?{urllib.parse.urlencode(params)}" if params else url
        return self._request("GET", full_url, headers=headers, body=None)

    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """POST ``payload`` as JSON and return the decoded JSON body."""
        body = json.dumps(payload).encode("utf-8")
        all_headers = {"Content-Type": "application/json", **(headers or {})}
        return self._request("POST", url, headers=all_headers, body=body)

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        body: bytes | None,
    ) -> Any:
        safe_url = _without_query(url)
        request_headers = {"Accept": "application/json", "User-Agent": self._user_agent}
        request_headers.update(headers or {})

        for attempt in range(1, self._retries + 2):  # first try + retries
            request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
            try:
                response = self._transport(request, self._timeout)
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt > self._retries:
                    raise HttpError(f"{method} {safe_url} failed: {exc}") from exc
                self._wait(attempt, None, f"network error ({exc})")
                continue

            if response.status in RETRYABLE_STATUS and attempt <= self._retries:
                retry_after = response.headers.get("Retry-After")
                self._wait(attempt, retry_after, f"HTTP {response.status}")
                continue

            if not 200 <= response.status < 300:
                raise HttpError(
                    f"{method} {safe_url} returned HTTP {response.status}",
                    status=response.status,
                )

            try:
                return json.loads(response.body)
            except ValueError as exc:
                raise HttpError(f"{method} {safe_url} returned invalid JSON") from exc

        raise AssertionError("unreachable")  # pragma: no cover

    def _wait(self, attempt: int, retry_after: str | None, reason: str) -> None:
        delay = self._backoff * 2 ** (attempt - 1)
        if retry_after is not None:
            with contextlib.suppress(ValueError):  # non-numeric Retry-After: keep backoff
                delay = min(float(retry_after), MAX_RETRY_AFTER_SECONDS)
        logger.warning("%s, retrying in %.1fs (attempt %d)", reason, delay, attempt)
        self._sleep(delay)


def _without_query(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
