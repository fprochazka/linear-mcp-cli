"""The Linear source of cli-watch-kit: one GraphQL request per tick for every due target of an account.

Targets:
- `issue <ID>`: one issue by identifier or UUID. Several issues are several watchers, which the daemon batches.
- `team <KEY>`, `cycle <KEY>/active|<N>`, `view <slugId>`: an issue scope.

Each target adds aliases to the tick's document. An issue watch always reads its issues, with the comments changed
since the newest change it saw. A scope watch reads (1) its known issues that changed or got a changed comment, and
(2) other issues of the scope that changed, which are candidates to enter. Issues leave when a change moves them out
of the scope (team, cycle, archive) or when a relist of the scope no longer has them: on a cycle rollover, a view
edit, and every ten minutes, because those leave the issues untouched.

`since` comes from the data (the newest `updatedAt` seen), so the snapshot stays the same while nothing changes; the
queries overlap it by a few seconds and the diff drops what was already seen.
"""

from __future__ import annotations

import time
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from cli_watch_kit.budget import DimensionSpec
from cli_watch_kit.events import KindCatalog, RawEvent
from cli_watch_kit.source import (
    NotFound,
    Params,
    PollContext,
    PollItem,
    PollOutcome,
    Source,
    SourceError,
    Target,
    Unauthorized,
)

from linear_mcp.watch import queries as q
from linear_mcp.watch.diff import (
    Actors,
    attachment_details,
    compact_issue,
    diff_comments,
    diff_issue,
    is_closed,
    newest,
)
from linear_mcp.watch.graphql import GraphQLResult, LinearGraphQL

type Snapshot = dict[str, Any]

STATUS = (
    "state_changed",
    "assignee_changed",
    "delegate_changed",
    "priority_changed",
    "labels_changed",
    "title_changed",
    "project_changed",
    "cycle_changed",
)
COMMENTS = ("comment_created", "comment_edited", "comment_resolved", "comment_unresolved")
LINKS = ("attachment_added",)
SCOPE = ("issue_entered", "issue_left")

CATALOG = KindCatalog(
    {
        "issue": (*STATUS, *COMMENTS, "comment_deleted", *LINKS),
        "team": (*STATUS, *COMMENTS, *LINKS, *SCOPE),
        "cycle": (*STATUS, *COMMENTS, *LINKS, *SCOPE, "active_cycle_changed"),
        "view": (*STATUS, *COMMENTS, *LINKS, *SCOPE),
    },
    groups={
        "status": STATUS,
        "comments": (*COMMENTS, "comment_deleted"),
        "links": LINKS,
        "scope": (*SCOPE, "active_cycle_changed"),
    },
)

ISSUE_INTERVAL = 30.0
SCOPE_INTERVAL = 60.0
OVERLAP = timedelta(seconds=5)
RELIST_EVERY = 600.0
MAX_PAGES = 4
MAX_COMMENTS = 400
# Complexity points per target and tick until X-Complexity corrects them; a team or cycle tick measured about 160.
ESTIMATE = {"issue": 25.0, "scope": 160.0, "baseline": 400.0}


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def overlap(since: str) -> str:
    return iso(parse_iso(since) - OVERLAP)


def scope_filter(target: Target, snapshot: Snapshot | None) -> dict[str, Any] | None:
    """The IssueFilter of a scope target; for a view only once its filter is known."""
    if target.kind == "team":
        return {"team": {"key": {"eq": target.id}}}
    if target.kind == "cycle":
        key, cycle = target.id.split("/", 1)
        which = {"isActive": {"eq": True}} if cycle == "active" else {"number": {"eq": float(cycle)}}
        return {"team": {"key": {"eq": key}}, "cycle": which}
    if target.kind == "view":
        view = (snapshot or {}).get("view")
        return view_filter(view) if view else None
    raise ValueError(f"not a scope: {target.kind}")


def view_filter(view: Mapping[str, Any]) -> dict[str, Any]:
    parts = [view.get("filterData") or {}]
    if view.get("team_id"):
        parts.append({"team": {"id": {"eq": view["team_id"]}}})
    return {"and": [p for p in parts if p]} if any(parts) else {}


def still_in_scope(target: Target, issue: Mapping[str, Any], snapshot: Snapshot) -> bool | None:
    """Whether a changed known issue is still in a team or cycle scope; `None` when only the server can tell."""
    if issue.get("archivedAt"):
        return False
    if target.kind == "team":
        return bool(issue.get("team") == target.id)
    if target.kind == "cycle":
        key, cycle = target.id.split("/", 1)
        if issue.get("team") != key:
            return False
        if cycle == "active":
            active = snapshot.get("active_cycle") or {}
            return issue.get("cycle") is not None and issue.get("cycle") == active.get("number")
        return str(issue.get("cycle")) == cycle
    return None


@dataclass
class Document:
    """The aliases, variable declarations and values of one tick's request."""

    selections: list[str] = field(default_factory=list)
    declarations: dict[str, str] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)

    def var(self, name: str, type_: str, value: Any) -> str:
        self.declarations[name] = type_
        self.variables[name] = value
        return name

    def text(self) -> str:
        decls = ", ".join(f"${name}: {type_}" for name, type_ in self.declarations.items())
        head = f"query Watch({decls})" if decls else "query Watch"
        return q.with_fragments(head + " {\n  " + "\n  ".join(self.selections) + "\n}")


class LinearSource(Source[Snapshot]):
    catalog = CATALOG
    # Linear documents 2,500 requests and 3M complexity points an hour for an API key; the readings replace these.
    dimensions = {
        "requests": DimensionSpec(per_minute=40, burst=10),
        "complexity": DimensionSpec(per_minute=50_000, burst=10_000),
    }
    batch_cost_cap = {"complexity": 5_000.0}

    def __init__(self, client: LinearGraphQL | None = None, clock: Any = time.time) -> None:
        self.client = client or LinearGraphQL()
        self.clock = clock
        self._viewers: dict[str, str] = {}

    async def account(self, target: Target, params: Params) -> str:
        key = str(params.get("api_key") or "")
        if not key:
            raise Unauthorized("no Linear API key in the subscription")
        viewer = self._viewers.get(key)
        if viewer is None:
            result = await self.client.query(key, q.VIEWER)
            viewer = str((result.data.get("viewer") or {}).get("id") or "")
            if not viewer:
                raise Unauthorized("Linear did not say whose API key this is")
            self._viewers[key] = viewer
        return viewer

    def batch_key(self, target: Target) -> Hashable | None:
        return "graphql"

    def interval(self, target: Target, snapshot: Snapshot | None) -> float:
        return ISSUE_INTERVAL if target.kind == "issue" else SCOPE_INTERVAL

    def cost(self, batch: Sequence[PollItem[Snapshot]]) -> Mapping[str, float]:
        complexity = 0.0
        for item in batch:
            if item.snapshot is None:
                complexity += ESTIMATE["baseline"]
            else:
                complexity += ESTIMATE["issue" if item.target.kind == "issue" else "scope"]
        return {"requests": 1.0, "complexity": complexity}

    def diff(self, target: Target, previous: Snapshot, current: Snapshot, events: frozenset[str]) -> Sequence[RawEvent]:
        """What changed between a watcher's baseline and the current snapshot, for a watcher that resubscribes to a
        resource other watchers kept polling. Snapshots keep no history and no comment bodies, so these events name
        no actor, and a comment created in the gap is reported by id only (its file is not written)."""
        nobody = Actors([], None, None)
        found: list[RawEvent] = []
        if target.kind == "issue":
            old_issues, new_issues = previous.get("issues") or {}, current.get("issues") or {}
            for key, issue in new_issues.items():
                if key in old_issues:
                    found += diff_issue(old_issues[key], issue, nobody)
                before = set((previous.get("comment_ids") or {}).get(key) or [])
                after = set((current.get("comment_ids") or {}).get(key) or [])
                for cid in sorted(after - before):
                    found.append(RawEvent("comment_created", {**_ref(issue), "comment_id": cid, "gap": True}))
                for cid in sorted(before - after):
                    found.append(RawEvent("comment_deleted", {**_ref(issue), "comment_id": cid, "gap": True}))
        else:
            old_members, new_members = previous.get("members") or {}, current.get("members") or {}
            before_cycle, after_cycle = previous.get("active_cycle"), current.get("active_cycle")
            if target.kind == "cycle" and _id(before_cycle) != _id(after_cycle):
                found.append(
                    RawEvent(
                        "active_cycle_changed",
                        {
                            "team": target.id.split("/")[0],
                            "from": (before_cycle or {}).get("number"),
                            "to": (after_cycle or {}).get("number"),
                        },
                    )
                )
            for uid, issue in new_members.items():
                if uid in old_members:
                    found += diff_issue(old_members[uid], issue, nobody)
                else:
                    found.append(
                        RawEvent(
                            "issue_entered",
                            {
                                **_ref(issue),
                                "state": (issue.get("state") or {}).get("name"),
                                "assignee": (issue.get("assignee") or {}).get("name"),
                            },
                        )
                    )
            for uid in sorted(set(old_members) - set(new_members)):
                issue = old_members[uid]
                found.append(
                    RawEvent(
                        "issue_left", {**_ref(issue), "reason": "gap", "state": (issue.get("state") or {}).get("name")}
                    )
                )
        return [e for e in found if e.kind in events]

    def summary(self, target: Target, snapshot: Snapshot | None) -> dict[str, Any]:
        if not snapshot:
            return {}
        if target.kind == "issue":
            return {
                "issues": [
                    {
                        "issue": i.get("identifier"),
                        "title": i.get("title"),
                        "state": (i.get("state") or {}).get("name"),
                        "assignee": (i.get("assignee") or {}).get("name"),
                        "url": i.get("url"),
                    }
                    for i in snapshot.get("issues", {}).values()
                ]
            }
        members = snapshot.get("members", {})
        summary: dict[str, Any] = {"issues": len(members)}
        if snapshot.get("active_cycle"):
            summary["active_cycle"] = snapshot["active_cycle"].get("number")
        if snapshot.get("view"):
            summary["view"] = snapshot["view"].get("name") or target.id
        return summary

    def status(self) -> dict[str, Any]:
        c = self.client.counters
        return {
            "requests": c.requests,
            "complexity": c.complexity,
            "last_complexity": c.last_complexity,
            "errors": c.errors,
        }

    async def poll(self, batch: Sequence[PollItem[Snapshot]], ctx: PollContext) -> Mapping[str, PollOutcome[Snapshot]]:
        key = str(ctx.params.get("api_key") or "")
        doc = Document()
        plans: list[Plan] = []
        for n, item in enumerate(batch):
            plan: Plan = IssuePlan(self, item, ctx, n) if item.target.kind == "issue" else ScopePlan(self, item, ctx, n)
            plan.add(doc)
            plans.append(plan)
        result = await self.client.query(key, doc.text(), doc.variables, ctx) if doc.selections else GraphQLResult({})
        outcomes: dict[str, PollOutcome[Snapshot]] = {}
        for plan in plans:
            try:
                outcomes[plan.item.key] = await plan.finish(result)
            except SourceError as exc:
                outcomes[plan.item.key] = PollOutcome(error=exc)
        return outcomes

    # Follow-up requests, each charged to the poll through the context.

    async def pages(
        self, ctx: PollContext, document: str, variables: dict[str, Any], path: str
    ) -> list[dict[str, Any]]:
        key = str(ctx.params["api_key"])
        nodes: list[dict[str, Any]] = []
        after: str | None = None
        for _ in range(MAX_PAGES):
            result = await self.client.query(key, document, {**variables, "after": after}, ctx)
            error = result.error_for("r")
            if error is not None:
                raise error
            connection: Any = result.data.get("r") or {}
            if path:
                connection = connection.get(path) or {}
            nodes.extend(connection.get("nodes") or [])
            info = connection.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                break
            after = info.get("endCursor")
        return nodes

    async def issues_by_id(self, ctx: PollContext, ids: Sequence[str]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        for start in range(0, len(ids), 250):
            chunk = list(ids[start : start + 250])
            nodes += await self.pages(ctx, q.PAGE_ISSUES, {"f": {"id": {"in": chunk}}}, "")
        return nodes


class Plan:
    def __init__(self, source: LinearSource, item: PollItem[Snapshot], ctx: PollContext, n: int) -> None:
        self.source = source
        self.item = item
        self.ctx = ctx
        self.n = n
        self.target = item.target
        self.snapshot = item.snapshot
        self.viewer = ctx.account or None

    def add(self, doc: Document) -> None:
        raise NotImplementedError

    async def finish(self, result: GraphQLResult) -> PollOutcome[Snapshot]:
        raise NotImplementedError

    def now_iso(self, result: GraphQLResult, seen: list[str | None]) -> str:
        """Where a baseline starts: Linear's time from the response, else the newest time it showed. Never the
        local clock, which can run ahead of Linear's and skip what happened in between."""
        if result.server_time is not None:
            return iso(result.server_time)
        return newest(seen) or iso(datetime.fromtimestamp(0, UTC))


class IssuePlan(Plan):
    """An issue watch: the issue every time, its comments changed since `since`, and all its comment ids."""

    def requested(self) -> list[str]:
        return [self.target.id]

    def add(self, doc: Document) -> None:
        snapshot = self.snapshot or {}
        known = snapshot.get("issues") or {}
        ids = [known[r]["id"] if r in known else r for r in self.requested()]
        since = overlap(snapshot["since"]) if snapshot.get("since") else "-PT1M"
        f = doc.var(f"f{self.n}", "IssueFilter!", {"id": {"in": ids}})
        s = doc.var(f"s{self.n}", "DateTimeOrDuration!", since)
        doc.selections.append(q.watched_issues(f"i{self.n}", f, s, len(ids) + 5))

    async def finish(self, result: GraphQLResult) -> PollOutcome[Snapshot]:
        alias = f"i{self.n}"
        error = result.error_for(alias)
        if error is not None:
            raise error
        nodes = (result.data.get(alias) or {}).get("nodes") or []
        previous = self.snapshot
        known = (previous or {}).get("issues") or {}
        by_key: dict[str, dict[str, Any]] = {}
        for requested in self.requested():
            uid = known[requested]["id"] if requested in known else None
            for node in nodes:
                if (
                    node["id"] == uid
                    or str(node.get("identifier", "")).upper() == requested.upper()
                    or (uid is None and node["id"] == requested)
                ):
                    by_key[requested] = node
        missing = [r for r in self.requested() if r not in by_key]
        if missing and previous is None:
            raise NotFound(f"no issue {missing[0]} (or no access to it)")
        if missing:
            return PollOutcome(previous, ended="not_found", end_data={"issues": missing})

        since = (previous or {}).get("since")
        since_q = overlap(since) if since else None
        events: list[RawEvent] = []
        issues: dict[str, Any] = {}
        comments: dict[str, Any] = dict((previous or {}).get("comments") or {})
        comment_ids: dict[str, list[str]] = {}
        stamps: list[str | None] = [since]
        for requested, node in by_key.items():
            issue = compact_issue(node)
            issues[requested] = issue
            stamps.append(issue.get("updatedAt"))
            comment_nodes = (node.get("comments") or {}).get("nodes") or []
            stamps += [c.get("updatedAt") for c in comment_nodes]
            all_ids = [c["id"] for c in (node.get("allComments") or {}).get("nodes") or []]
            comment_ids[requested] = sorted(all_ids)
            if previous is None or requested not in known:
                # The baseline remembers no comment: a later change to one is judged by its own times.
                continue
            actors = Actors((node.get("history") or {}).get("nodes") or [], since_q, self.viewer)
            events += attachment_details(diff_issue(known[requested], issue, actors), node)
            found, seen = diff_comments(comments, comment_nodes, issue, since_q, self.viewer)
            events += found
            comments.update(seen)
            before_ids = set(((previous or {}).get("comment_ids") or {}).get(requested) or [])
            if len(all_ids) < 250:
                for gone in sorted(before_ids - set(all_ids)):
                    events.append(
                        RawEvent(
                            "comment_deleted",
                            {
                                "issue": issue.get("identifier"),
                                "title": issue.get("title"),
                                "url": issue.get("url"),
                                "comment_id": gone,
                            },
                        )
                    )
                    comments.pop(gone, None)
        snapshot: Snapshot = {
            "issues": issues,
            "comments": _prune(comments),
            "comment_ids": comment_ids,
            # The baseline starts at Linear's time of the poll: a comment does not move its issue's updatedAt, so
            # the issue's time could be older than comments that already exist.
            "since": newest([*stamps, self.now_iso(result, stamps)]) if previous is None else newest(stamps),
        }
        ended = None
        end_data: dict[str, Any] = {}
        # Only a change ends it: an issue that was already closed when the watch started keeps being watched.
        (now,) = issues.values()
        if previous is not None and is_closed(now) and not all(is_closed(i) for i in known.values()):
            ended = "archived" if now.get("archivedAt") else str((now.get("state") or {}).get("type"))
            end_data = {"issue": now.get("identifier"), "state": (now.get("state") or {}).get("name")}
        return PollOutcome(snapshot, events, ended=ended, end_data=end_data)


class ScopePlan(Plan):
    """A team, cycle or view watch."""

    def add(self, doc: Document) -> None:
        snapshot = self.snapshot
        if self.target.kind == "view":
            v = doc.var(f"v{self.n}k", "String!", self.target.id)
            doc.selections.append(q.VIEW.format(alias=f"v{self.n}", var=v))
        else:
            t = doc.var(f"t{self.n}k", "String!", self.target.id.split("/", 1)[0])
            doc.selections.append(q.TEAM.format(alias=f"t{self.n}", var=t))
        scope = scope_filter(self.target, snapshot)
        if snapshot is None or scope is None:
            return
        since = overlap(snapshot["since"])
        members = sorted(snapshot.get("members") or {})
        s = doc.var(f"s{self.n}", "DateTimeOrDuration!", since)
        if members:
            m = doc.var(f"m{self.n}", "IssueFilter!", {"id": {"in": members}})
            doc.selections.append(q.changed_issues(f"k{self.n}", m, s, 100))
        candidates = {"and": [scope, {"id": {"nin": members}}]} if members else scope
        c = doc.var(f"c{self.n}", "IssueFilter!", candidates)
        doc.selections.append(q.changed_issues(f"e{self.n}", c, s, 50))

    def header(self, result: GraphQLResult) -> dict[str, Any]:
        alias = f"v{self.n}" if self.target.kind == "view" else f"t{self.n}"
        error = result.error_for(alias)
        if error is not None:
            raise error
        node = result.data.get(alias)
        if not node:
            what = "view" if self.target.kind == "view" else "team"
            raise NotFound(f"no {what} {self.target.id.split('/', 1)[0]} (or no access to it)")
        return dict(node)

    async def relist(self, snapshot: Snapshot, baseline: bool) -> list[dict[str, Any]]:
        """The scope's issues as the server sees them now, with the issue fields."""
        ctx = self.ctx
        if self.target.kind == "view":
            ids = [n["id"] for n in await self.source.pages(ctx, q.PAGE_VIEW_IDS, {"v": self.target.id}, "issues")]
            members = snapshot.get("members") or {}
            fetch = ids if baseline else [i for i in ids if i not in members]
            fetched = {n["id"]: n for n in await self.source.issues_by_id(ctx, fetch)}
            # Known members keep their stored state here; their changes come from the change query.
            return [fetched.get(i, {"id": i, "_known": True}) for i in ids]
        scope = scope_filter(self.target, snapshot)
        assert scope is not None
        if self.target.kind == "team":
            # A team's history is unbounded: start from its open issues, then follow what changes.
            scope = {"and": [scope, {"state": {"type": {"nin": ["completed", "canceled"]}}}]}
        if baseline:
            return await self.source.pages(ctx, q.PAGE_ISSUES, {"f": scope}, "")
        ids = await self._ids(scope)
        members = snapshot.get("members") or {}
        fetched = {n["id"]: n for n in await self.source.issues_by_id(ctx, [i for i in ids if i not in members])}
        return [fetched.get(i, {"id": i, "_known": True}) for i in ids]

    async def _ids(self, scope: dict[str, Any]) -> list[str]:
        return [n["id"] for n in await self.source.pages(self.ctx, q.PAGE_IDS, {"f": scope}, "")]

    async def finish(self, result: GraphQLResult) -> PollOutcome[Snapshot]:
        head = self.header(result)
        previous = self.snapshot
        snapshot: Snapshot = {
            "members": dict((previous or {}).get("members") or {}),
            "comments": dict((previous or {}).get("comments") or {}),
            "since": (previous or {}).get("since"),
        }
        events: list[RawEvent] = []
        relist_due = previous is None or self.source.clock() - self.item.state.get("relisted_at", 0.0) > RELIST_EVERY

        if self.target.kind == "cycle":
            snapshot["active_cycle"] = head.get("activeCycle")
            before = (previous or {}).get("active_cycle")
            if (
                previous is not None
                and self.target.id.endswith("/active")
                and _id(before) != _id(head.get("activeCycle"))
            ):
                events.append(
                    RawEvent(
                        "active_cycle_changed",
                        {
                            "team": self.target.id.split("/")[0],
                            "from": (before or {}).get("number"),
                            "to": (head.get("activeCycle") or {}).get("number"),
                        },
                    )
                )
                relist_due = True
        if self.target.kind == "view":
            view = {
                "updatedAt": head.get("updatedAt"),
                "filterData": head.get("filterData") or {},
                "team_id": (head.get("team") or {}).get("id"),
            }
            snapshot["view"] = view
            if previous is not None and (previous.get("view") or {}).get("updatedAt") != view["updatedAt"]:
                relist_due = True

        if previous is None:
            nodes = await self.relist(snapshot, baseline=True)
            snapshot["members"] = {n["id"]: compact_issue(n) for n in nodes}
            seen = [i.get("updatedAt") for i in snapshot["members"].values()]
            snapshot["since"] = newest([*seen, self.now_iso(result, seen)])
            self.item.state["relisted_at"] = self.source.clock()
            return PollOutcome(snapshot)

        since = str(previous.get("since"))
        since_q = overlap(since)
        members: dict[str, Any] = snapshot["members"]
        stamps: list[str | None] = [since]
        candidates = False

        def comment_events(node: Mapping[str, Any], issue: dict[str, Any]) -> None:
            comment_nodes = (node.get("comments") or {}).get("nodes") or []
            stamps.extend(c.get("updatedAt") for c in comment_nodes)
            found, seen = diff_comments(snapshot["comments"], comment_nodes, issue, since_q, self.viewer)
            events.extend(found)
            snapshot["comments"].update(seen)

        for node in await self._connection(result, f"k{self.n}", {"id": {"in": sorted(members)}}, since_q):
            issue = compact_issue(node)
            stamps.append(issue.get("updatedAt"))
            old = members.get(issue["id"])
            if old is None:
                continue
            actors = Actors((node.get("history") or {}).get("nodes") or [], since_q, self.viewer)
            events += attachment_details(diff_issue(old, issue, actors), node)
            comment_events(node, issue)
            inside = still_in_scope(self.target, issue, snapshot)
            if inside is False:
                members.pop(issue["id"], None)
                reason = "archived" if issue.get("archivedAt") else "moved"
                events.append(
                    RawEvent(
                        "issue_left", {**_ref(issue), "reason": reason, "state": (issue.get("state") or {}).get("name")}
                    )
                )
            else:
                members[issue["id"]] = issue
                if inside is None:
                    candidates = True  # a view: whether it still matches is settled by the relist

        scope = scope_filter(self.target, previous)
        if scope is not None:
            nin = {"and": [scope, {"id": {"nin": sorted(members)}}]} if members else scope
            for node in await self._connection(result, f"e{self.n}", nin, since_q):
                issue = compact_issue(node)
                stamps.append(issue.get("updatedAt"))
                if issue["id"] in members:
                    continue
                if self.target.kind == "view":
                    candidates = True
                    continue
                if self.target.kind == "team" and is_closed(issue) and str(issue.get("createdAt") or "") <= since_q:
                    # An old closed issue that got touched: follow it from now on without announcing it.
                    members[issue["id"]] = issue
                    comment_events(node, issue)
                    continue
                members[issue["id"]] = issue
                events.append(
                    RawEvent(
                        "issue_entered",
                        {
                            **_ref(issue),
                            "state": (issue.get("state") or {}).get("name"),
                            "assignee": (issue.get("assignee") or {}).get("name"),
                        },
                    )
                )
                comment_events(node, issue)

        if self.target.kind == "view" and candidates:
            relist_due = True
        if relist_due and self.target.kind in ("cycle", "view"):
            nodes = await self.relist(snapshot, baseline=False)
            now_ids = {n["id"] for n in nodes}
            for uid in sorted(set(members) - now_ids):
                issue = members.pop(uid)
                events.append(
                    RawEvent(
                        "issue_left",
                        {**_ref(issue), "reason": "relisted", "state": (issue.get("state") or {}).get("name")},
                    )
                )
            for node in nodes:
                if node.get("_known") or node["id"] in members:
                    continue
                issue = compact_issue(node)
                members[issue["id"]] = issue
                events.append(
                    RawEvent(
                        "issue_entered",
                        {
                            **_ref(issue),
                            "state": (issue.get("state") or {}).get("name"),
                            "assignee": (issue.get("assignee") or {}).get("name"),
                        },
                    )
                )
            self.item.state["relisted_at"] = self.source.clock()

        snapshot["since"] = newest(stamps, since)
        snapshot["comments"] = _prune(snapshot["comments"])
        return PollOutcome(snapshot, events)

    async def _connection(
        self, result: GraphQLResult, alias: str, filter_: dict[str, Any], since: str
    ) -> list[dict[str, Any]]:
        if alias not in result.data and alias not in result.errors:
            return []
        error = result.error_for(alias)
        if error is not None:
            raise error
        connection = result.data.get(alias) or {}
        nodes = list(connection.get("nodes") or [])
        info = connection.get("pageInfo") or {}
        if info.get("hasNextPage"):
            nodes += await self.source.pages(self.ctx, q.PAGE_CHANGED, {"f": filter_, "s": since}, "")
            seen: dict[str, dict[str, Any]] = {}
            for node in nodes:
                seen[node["id"]] = node
            nodes = list(seen.values())
        return nodes


def _id(node: Any) -> Any:
    return node.get("id") if isinstance(node, dict) else None


def _ref(issue: Mapping[str, Any]) -> dict[str, Any]:
    return {"issue": issue.get("identifier"), "title": issue.get("title"), "url": issue.get("url")}


def _prune(comments: dict[str, Any]) -> dict[str, Any]:
    if len(comments) <= MAX_COMMENTS:
        return comments
    ordered = sorted(comments.items(), key=lambda kv: str(kv[1].get("updatedAt") or ""), reverse=True)
    return dict(ordered[:MAX_COMMENTS])
