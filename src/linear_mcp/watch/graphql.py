"""A small async client of Linear's GraphQL API that maps failures to cli-watch-kit's source errors.

Each response's rate-limit headers go to the poll's budget, and its `X-Complexity` is charged as what it really cost.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from cli_watch_kit.source import NotFound, PollContext, RateLimited, SourceError, Transient, Unauthorized

API_URL = "https://api.linear.app/graphql"
USER_AGENT = "linear-watch (linear-mcp-cli)"
DIMENSION_HEADERS = {"requests": "x-ratelimit-requests", "complexity": "x-ratelimit-complexity"}


@dataclass
class GraphQLResult:
    """The `data` of one response, and its errors by the top-level alias they belong to (`""` for none)."""

    data: Mapping[str, Any]
    errors: dict[str, list[str]] = field(default_factory=dict)
    complexity: float | None = None
    server_time: datetime | None = None
    """The response's `Date`: Linear's clock, which the watch's times compare with, not the local one."""

    def error_for(self, alias: str) -> SourceError | None:
        messages = self.errors.get(alias)
        if not messages:
            return None
        text = "; ".join(messages)
        if any("not found" in m.lower() for m in messages):
            return NotFound(text)
        return Transient(text)


@dataclass
class Counters:
    requests: int = 0
    complexity: float = 0.0
    last_complexity: float | None = None
    errors: int = 0


class LinearGraphQL:
    """One shared `httpx.AsyncClient`; the key travels with each call, so several accounts can share the client."""

    def __init__(self, url: str = API_URL, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 30.0):
        self.url = url
        self._transport = transport
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self.counters = Counters()

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                transport=self._transport, timeout=self._timeout, headers={"User-Agent": USER_AGENT}
            )
        return self._client

    async def query(
        self, key: str, document: str, variables: Mapping[str, Any] | None = None, ctx: PollContext | None = None
    ) -> GraphQLResult:
        ctx = ctx if ctx is not None else PollContext.current()
        try:
            response = await self._http().post(
                self.url,
                json={"query": document, "variables": dict(variables or {})},
                headers={"Authorization": key, "Content-Type": "application/json"},
            )
        except httpx.HTTPError as exc:
            self.counters.errors += 1
            raise Transient(f"Linear did not answer: {type(exc).__name__}: {exc}") from exc
        self.counters.requests += 1
        complexity = _number(response.headers.get("x-complexity"))
        if ctx is not None:
            _observe(ctx, response.headers)
            ctx.spend({"requests": 1.0, **({"complexity": complexity} if complexity is not None else {})})
        if complexity is not None:
            self.counters.complexity += complexity
            self.counters.last_complexity = complexity
        result = _result(response, complexity)
        result.server_time = _date(response.headers.get("date"))
        return result


def _number(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _observe(ctx: PollContext, headers: httpx.Headers) -> None:
    now = ctx.clock()
    for dimension, prefix in DIMENSION_HEADERS.items():
        remaining = _number(headers.get(f"{prefix}-remaining"))
        reset_ms = _number(headers.get(f"{prefix}-reset"))
        # Linear sends the reset as Unix milliseconds; the budget compares it with wall-clock seconds.
        reset_at = reset_ms / 1000 if reset_ms is not None else None
        ctx.budget.observe(dimension, now, remaining=remaining, reset_at=reset_at)


def _retry_after(headers: httpx.Headers) -> float | None:
    value = _number(headers.get("retry-after"))
    if value is not None:
        return value
    reset = _number(headers.get("x-ratelimit-requests-reset"))
    return max(0.0, reset / 1000 - time.time()) if reset is not None else None


def _codes(body: Any) -> list[str]:
    errors = body.get("errors") if isinstance(body, dict) else None
    codes = []
    for error in errors or []:
        extensions = error.get("extensions") if isinstance(error, dict) else None
        if isinstance(extensions, dict) and isinstance(extensions.get("code"), str):
            codes.append(extensions["code"].upper())
    return codes


def _messages(body: Any) -> str:
    errors = body.get("errors") if isinstance(body, dict) else None
    return "; ".join(str(e.get("message")) for e in errors or [] if isinstance(e, dict)) or "no error message"


def _result(response: httpx.Response, complexity: float | None) -> GraphQLResult:
    try:
        body = response.json()
    except ValueError:
        body = None
    codes = _codes(body)
    status = response.status_code
    if status == 429 or "RATELIMITED" in codes:
        raise RateLimited(f"Linear rate limit: {_messages(body)}", retry_after=_retry_after(response.headers))
    if status in (401, 403) or "AUTHENTICATION_ERROR" in codes or "FORBIDDEN" in codes:
        raise Unauthorized(f"Linear refused the API key: {_messages(body)}")
    if status >= 500:
        raise Transient(f"Linear answered HTTP {status}")
    if not isinstance(body, dict) or (status != 200 and not body.get("data")):
        raise Transient(f"Linear answered HTTP {status}: {_messages(body)}")
    data = body.get("data") or {}
    errors: dict[str, list[str]] = {}
    for error in body.get("errors") or []:
        if not isinstance(error, dict):
            continue
        path = error.get("path") or [""]
        errors.setdefault(str(path[0]), []).append(str(error.get("message")))
    if errors.get("") and not data:
        raise Transient(f"Linear refused the query: {'; '.join(errors[''])}")
    return GraphQLResult(data if isinstance(data, dict) else {}, errors, complexity)
