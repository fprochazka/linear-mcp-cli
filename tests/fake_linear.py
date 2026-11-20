"""A recorded stand-in for Linear's GraphQL endpoint, behind `httpx.MockTransport`, and node builders for its answers.

A test sets what the next tick's aliases return (`watch`), what the paged follow-ups return (`pages`, `ids`,
`view_ids`), or a failure (`fail`), then polls the source. Every request is recorded.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Any

import httpx
from cli_watch_kit.budget import Budget
from cli_watch_kit.daemon.cache import ByteBoundedCache
from cli_watch_kit.source import PollContext, PollItem, PollOutcome, Target

from linear_mcp.watch.graphql import LinearGraphQL
from linear_mcp.watch.source import CATALOG, LinearSource

VIEWER = "user-me"
NOW = datetime(2026, 1, 10, 10, 0, 0, tzinfo=UTC)
BEFORE = "2026-01-10T09:00:00.000Z"
AFTER = "2026-01-10T10:00:30.000Z"
LATER = "2026-01-10T10:01:30.000Z"

TODO = {"id": "state-todo", "name": "Todo", "type": "unstarted"}
DOING = {"id": "state-doing", "name": "In Progress", "type": "started"}
DONE = {"id": "state-done", "name": "Done", "type": "completed"}
TRIAGE = {"id": "state-triage", "name": "Triage", "type": "triage"}
BACKLOG = {"id": "state-backlog", "name": "Backlog", "type": "backlog"}
DECLINED = {"id": "state-declined", "name": "Declined", "type": "canceled"}


def issue(
    identifier: str,
    *,
    state: Mapping[str, Any] = TODO,
    updated: str = BEFORE,
    created: str = "2026-01-01T00:00:00.000Z",
    team: str = "ABC",
    cycle: int | None = None,
    comments: Sequence[Mapping[str, Any]] = (),
    all_comments: Sequence[str] | None = None,
    history: Sequence[Mapping[str, Any]] = (),
    assignee: str | None = None,
    creator: str | None = None,
    bot: str | None = None,
) -> dict[str, Any]:
    """An issue node; `assignee="me"` assigns it to the viewer."""
    return {
        "id": f"uuid-{identifier}",
        "identifier": identifier,
        "title": f"Title of {identifier}",
        "url": f"https://linear.app/example/issue/{identifier}",
        "updatedAt": updated,
        "createdAt": created,
        "archivedAt": None,
        "priority": 3,
        "state": dict(state),
        "assignee": {"id": f"user-{assignee}", "name": assignee} if assignee else None,
        "delegate": None,
        "cycle": {"id": f"cycle-{cycle}", "number": cycle} if cycle is not None else None,
        "project": None,
        "team": {"id": f"team-{team}", "key": team},
        "labels": {"nodes": []},
        "attachments": {"nodes": []},
        "comments": {"nodes": list(comments)},
        "allComments": {"nodes": [{"id": c} for c in (all_comments if all_comments is not None else [])]},
        "history": {"nodes": list(history)},
        "creator": {"id": f"user-{creator}", "name": creator} if creator else None,
        "botActor": {"name": bot} if bot else None,
    }


def comment(
    cid: str,
    body: str,
    *,
    created: str = AFTER,
    updated: str | None = None,
    edited: str | None = None,
    resolved: str | None = None,
    user: str = "Jane",
) -> dict[str, Any]:
    return {
        "id": cid,
        "body": body,
        "createdAt": created,
        "updatedAt": updated or created,
        "editedAt": edited,
        "archivedAt": None,
        "resolvedAt": resolved,
        "parentId": None,
        "user": {"id": f"user-{user}", "name": user},
        "botActor": None,
    }


def history(created: str, *, actor: str = VIEWER, **fields: Any) -> dict[str, Any]:
    """A history row by the viewer, or by `actor="user-<Name>"`."""
    return {
        "id": f"h-{created}",
        "createdAt": created,
        "actor": {"id": actor, "name": "Me" if actor == VIEWER else actor.removeprefix("user-")},
        "botActor": None,
        **fields,
    }


def connection(nodes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"nodes": list(nodes), "pageInfo": {"hasNextPage": False, "endCursor": None}}


@dataclass
class FakeLinear:
    watch: dict[str, Any] = field(default_factory=dict)
    pages: list[dict[str, Any]] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    view_ids: list[str] = field(default_factory=list)
    check: dict[str, Any] = field(default_factory=dict)
    """The answer to the start check of a filter's teams and statuses."""
    fail: tuple[int, dict[str, str], dict[str, Any]] | None = None
    server_time: datetime = NOW
    script: list[dict[str, Any]] = field(default_factory=list)
    """Answers for the next tick documents, one per tick, taken before `watch`; the last one repeats."""
    requests: list[dict[str, Any]] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        headers = {
            "date": format_datetime(self.server_time, usegmt=True),
            "x-complexity": "42",
            "x-ratelimit-requests-remaining": "2400",
            "x-ratelimit-requests-reset": str(int(NOW.timestamp() * 1000) + 3_600_000),
            "x-ratelimit-complexity-remaining": "2900000",
            "x-ratelimit-complexity-reset": str(int(NOW.timestamp() * 1000) + 3_600_000),
        }
        if self.fail is not None:
            status, extra, payload = self.fail
            return httpx.Response(status, json=payload, headers={**headers, **extra})
        query: str = body["query"]
        unused = [n for n in re.findall(r"fragment (\w+) on", query) if f"...{n}" not in query]
        if unused:
            # As Linear does.
            errors = [{"message": f'Fragment "{n}" is never used.'} for n in unused]
            return httpx.Response(400, json={"errors": errors}, headers=headers)
        variables = body.get("variables") or {}
        if "query Watch" in query:
            if self.script:
                self.watch = self.script.pop(0) if len(self.script) > 1 else self.script[0]
            data = {alias: value for alias, value in self.watch.items() if f"{alias}:" in query}
        elif "query Page" in query:
            wanted = set(((variables.get("f") or {}).get("id") or {}).get("in") or [])
            nodes = [n for n in self.pages if not wanted or n["id"] in wanted]
            data = {"r": connection(nodes)}
        elif "query Ids" in query:
            data = {"r": connection([{"id": i} for i in self.ids])}
        elif "query ViewIds" in query:
            data = {"r": {"issues": connection([{"id": i} for i in self.view_ids])}}
        elif "query Check" in query:
            data = dict(self.check)
        elif "viewer" in query:
            data = {"viewer": {"id": VIEWER, "name": "Me", "organization": {"urlKey": "example"}}}
        else:
            raise AssertionError(f"unexpected query: {query[:80]}")
        return httpx.Response(200, json={"data": data}, headers=headers)


@dataclass
class Harness:
    """Polls one target as the engine would: the snapshot of each poll feeds the next."""

    target: Target
    fake: FakeLinear = field(default_factory=FakeLinear)
    snapshot: Any = None
    state: dict[str, Any] = field(default_factory=dict)
    clock: float = NOW.timestamp()

    def __post_init__(self) -> None:
        client = LinearGraphQL(transport=httpx.MockTransport(self.fake.handler))
        self.source = LinearSource(client, clock=lambda: self.clock)
        self.budget = Budget(dict(LinearSource.dimensions))

    def poll(self) -> PollOutcome[Any]:
        ctx = PollContext(VIEWER, {"api_key": "lin_api_test"}, self.budget, ByteBoundedCache(), lambda: self.clock)
        item = PollItem(self.target, self.snapshot, frozenset(CATALOG.produced(self.target.kind)), self.state)
        outcome = asyncio.run(self.source.poll([item], ctx))[self.target.key]
        if outcome.error is None and outcome.snapshot is not None:
            # Through JSON, as the engine keeps it and a baseline restores it.
            self.snapshot = json.loads(json.dumps(self.source.encode(outcome.snapshot)))
        return outcome


def kinds(outcome: PollOutcome[Any]) -> list[str]:
    return [e.kind for e in outcome.events]
