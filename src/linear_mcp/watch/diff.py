"""Pure functions: GraphQL nodes into compact snapshots, and two snapshots into events.

A compact issue keeps what the events compare (state, assignee, delegate, priority, title, labels, cycle, project,
attachments). A compact comment keeps a hash of its body and its edit and resolve times, which tell an edit and a
resolve from a reaction: all of them move `updatedAt`, only the first two change what is kept here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from cli_watch_kit.events import RawEvent

CLOSED_TYPES = frozenset({"completed", "canceled"})
EXCERPT = 300

Issue = dict[str, Any]
Comment = dict[str, Any]


def _name(node: Any) -> str | None:
    return node.get("name") if isinstance(node, dict) else None


def _id(node: Any) -> str | None:
    return node.get("id") if isinstance(node, dict) else None


def compact_issue(node: Mapping[str, Any]) -> Issue:
    state = node.get("state") or {}
    cycle = node.get("cycle") or {}
    labels = (node.get("labels") or {}).get("nodes") or []
    attachments = (node.get("attachments") or {}).get("nodes")
    issue: Issue = {
        "id": node["id"],
        "identifier": node.get("identifier"),
        "title": node.get("title"),
        "url": node.get("url"),
        "updatedAt": node.get("updatedAt"),
        "createdAt": node.get("createdAt"),
        "archivedAt": node.get("archivedAt"),
        "state": {"id": state.get("id"), "name": state.get("name"), "type": state.get("type")},
        "assignee": {"id": _id(node.get("assignee")), "name": _name(node.get("assignee"))}
        if node.get("assignee")
        else None,
        "delegate": {"id": _id(node.get("delegate")), "name": _name(node.get("delegate"))}
        if node.get("delegate")
        else None,
        "priority": node.get("priority"),
        "cycle": cycle.get("number") if cycle else None,
        "project": _name(node.get("project")),
        "team": (node.get("team") or {}).get("key"),
        "labels": sorted(str(label.get("name")) for label in labels),
    }
    if attachments is not None:
        issue["attachments"] = sorted(str(a["id"]) for a in attachments)
    return issue


def body_hash(body: str | None) -> str:
    return hashlib.sha256((body or "").encode()).hexdigest()[:16]


def compact_comment(node: Mapping[str, Any]) -> Comment:
    return {
        "updatedAt": node.get("updatedAt"),
        "editedAt": node.get("editedAt"),
        "resolvedAt": node.get("resolvedAt"),
        "body": body_hash(node.get("body")),
    }


def is_closed(issue: Issue) -> bool:
    return (issue.get("state") or {}).get("type") in CLOSED_TYPES or bool(issue.get("archivedAt"))


def _ref(issue: Issue) -> dict[str, Any]:
    return {"issue": issue.get("identifier"), "title": issue.get("title"), "url": issue.get("url")}


class Actors:
    """Who made the changes of one issue, from its newest history rows. Rows lag the issue by up to a few seconds,
    so a change without a matching row is attributed to nobody rather than guessed."""

    def __init__(self, rows: Sequence[Mapping[str, Any]], since: str | None, viewer: str | None) -> None:
        self.rows = [r for r in rows if since is None or str(r.get("createdAt") or "") > since]
        self.viewer = viewer

    def _who(self, row: Mapping[str, Any] | None) -> dict[str, Any]:
        if row is None:
            return {"actor": None, "actor_is_me": False}
        actor = row.get("actor")
        bot = row.get("botActor")
        name = _name(actor) or (f"{_name(bot)} (bot)" if _name(bot) else None)
        return {"actor": name, "actor_is_me": bool(actor and self.viewer and actor.get("id") == self.viewer)}

    def find(self, **match: Any) -> dict[str, Any]:
        for row in self.rows:
            if all((row.get(k) in v) if isinstance(v, (set, frozenset)) else row.get(k) == v for k, v in match.items()):
                return self._who(row)
        return self._who(None)

    def with_labels(self) -> dict[str, Any]:
        for row in self.rows:
            if row.get("addedLabelIds") or row.get("removedLabelIds"):
                return self._who(row)
        return self._who(None)

    def newest(self) -> dict[str, Any]:
        return self._who(self.rows[0] if self.rows else None)


def diff_issue(old: Issue, new: Issue, actors: Actors) -> list[RawEvent]:
    """What changed on one issue between two compact snapshots."""
    events: list[RawEvent] = []
    ref = _ref(new)
    old_state, new_state = old.get("state") or {}, new.get("state") or {}
    if old_state.get("id") != new_state.get("id"):
        who = actors.find(toStateId=new_state.get("id"))
        events.append(
            RawEvent(
                "state_changed",
                {
                    **ref,
                    "from": old_state.get("name"),
                    "to": new_state.get("name"),
                    "to_type": new_state.get("type"),
                    **who,
                },
            )
        )
    for field, kind, column in (
        ("assignee", "assignee_changed", "toAssigneeId"),
        ("delegate", "delegate_changed", None),
    ):
        before, after = old.get(field), new.get(field)
        if _id(before) != _id(after):
            who = actors.find(**{column: _id(after)}) if column else actors.newest()
            events.append(RawEvent(kind, {**ref, "from": _name(before), "to": _name(after), **who}))
    if old.get("labels") != new.get("labels"):
        added = sorted(set(new.get("labels") or []) - set(old.get("labels") or []))
        removed = sorted(set(old.get("labels") or []) - set(new.get("labels") or []))
        events.append(RawEvent("labels_changed", {**ref, "added": added, "removed": removed, **actors.with_labels()}))
    for field, kind in (
        ("priority", "priority_changed"),
        ("title", "title_changed"),
        ("project", "project_changed"),
        ("cycle", "cycle_changed"),
    ):
        if old.get(field) != new.get(field):
            events.append(RawEvent(kind, {**ref, "from": old.get(field), "to": new.get(field), **actors.newest()}))
    if "attachments" in new and "attachments" in old:
        for attachment in sorted(set(new["attachments"]) - set(old["attachments"])):
            who = actors.find(attachmentId=attachment)
            events.append(RawEvent("attachment_added", {**ref, "attachment_id": attachment, **who}))
    return events


def attachment_details(events: list[RawEvent], node: Mapping[str, Any]) -> list[RawEvent]:
    """Fill title, URL and source of `attachment_added` events from the issue node's attachments."""
    by_id = {a["id"]: a for a in (node.get("attachments") or {}).get("nodes") or []}
    out = []
    for event in events:
        if event.kind == "attachment_added" and event.data["attachment_id"] in by_id:
            a = by_id[event.data["attachment_id"]]
            data = {
                **event.data,
                "attachment_title": a.get("title"),
                "attachment_url": a.get("url"),
                "source": a.get("sourceType"),
            }
            event = RawEvent(event.kind, data, event.artifacts)
        out.append(event)
    return out


def diff_comments(
    known: Mapping[str, Comment],
    nodes: Iterable[Mapping[str, Any]],
    issue: Issue,
    since: str | None,
    viewer: str | None,
) -> tuple[list[RawEvent], dict[str, Comment]]:
    """Events for the comments that changed since `since`, and the comments to remember.

    A comment seen before is compared with what was kept of it. One not seen before is new when it was created after
    `since`; otherwise only an edit or a resolve after `since` is reported, because a reaction moves `updatedAt` too.
    """
    events: list[RawEvent] = []
    seen: dict[str, Comment] = {}
    for node in sorted(nodes, key=lambda n: str(n.get("createdAt") or "")):
        cid = str(node["id"])
        now = compact_comment(node)
        seen[cid] = now
        before = known.get(cid)
        kinds: list[str] = []
        if before is None:
            if since is None or str(node.get("createdAt") or "") > since:
                kinds.append("comment_created")
            elif node.get("editedAt") and str(node["editedAt"]) > since:
                kinds.append("comment_edited")
            elif node.get("resolvedAt") and str(node["resolvedAt"]) > since:
                kinds.append("comment_resolved")
        else:
            if before.get("body") != now["body"] or before.get("editedAt") != now["editedAt"]:
                kinds.append("comment_edited")
            if not before.get("resolvedAt") and now["resolvedAt"]:
                kinds.append("comment_resolved")
            elif before.get("resolvedAt") and not now["resolvedAt"]:
                kinds.append("comment_unresolved")
        for kind in kinds:
            events.append(RawEvent(kind, comment_data(node, issue, viewer)))
    return events, seen


def comment_data(node: Mapping[str, Any], issue: Issue, viewer: str | None) -> dict[str, Any]:
    user = node.get("user")
    bot = node.get("botActor")
    author = _name(user) or (f"{_name(bot)} (bot)" if _name(bot) else None)
    body = str(node.get("body") or "")
    return {
        **_ref(issue),
        "comment_id": node.get("id"),
        "parent_id": node.get("parentId"),
        "author": author,
        "actor": author,
        "actor_is_me": bool(user and viewer and user.get("id") == viewer),
        "created_at": node.get("createdAt"),
        "excerpt": body[:EXCERPT],
        "body": body,
    }


def newest(values: Iterable[str | None], default: str | None = None) -> str | None:
    present = [v for v in values if v]
    return max(present) if present else default
