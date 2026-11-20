"""The `filter` target of `linear watch issues`: issues of some teams, a cycle, assigned to me, or in some statuses.

The parts are AND-ed, the statuses OR-ed. A status matches a workflow state by name, case-insensitively, in each team's
own workflow; `triage` also matches the state type `triage`, so a renamed triage state still counts. `--assignee me`
without a status means the open issues only.

The target id is a canonical spelling of the parts (`team=ABC+DEF,cycle=active,assignee=me,status=backlog+triage`), so
the same filter typed in another order shares the daemon resource and the resource dir. The parts themselves travel
in the target's data.
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cli_watch_kit.source import Target

from linear_mcp.watch.diff import CLOSED_TYPES

TRIAGE = "triage"


@dataclass(frozen=True)
class FilterSpec:
    teams: tuple[str, ...] = ()
    cycle: str | None = None
    assignee_me: bool = False
    statuses: tuple[str, ...] = ()

    @classmethod
    def of(
        cls,
        teams: tuple[str, ...] = (),
        cycle: str | None = None,
        assignee_me: bool = False,
        statuses: tuple[str, ...] = (),
    ) -> FilterSpec:
        """Normalized: team keys upper case, statuses lower case and stripped, both sorted and without duplicates."""
        return cls(
            tuple(sorted({t.strip().upper() for t in teams if t.strip()})),
            cycle.lower() if cycle else None,
            assignee_me,
            tuple(sorted({s.strip().lower() for s in statuses if s.strip()})),
        )

    @classmethod
    def from_target(cls, target: Target) -> FilterSpec:
        data = target.data
        return cls.of(
            tuple(data.get("teams") or ()),
            data.get("cycle"),
            bool(data.get("assignee_me")),
            tuple(data.get("statuses") or ()),
        )

    @property
    def teams_only(self) -> bool:
        """Only teams: like a team watch, it starts from their open issues and follows closed ones once they change."""
        return bool(self.teams) and not (self.cycle or self.assignee_me or self.statuses)

    def target(self) -> Target:
        data = {"teams": list(self.teams), "cycle": self.cycle, "assignee_me": self.assignee_me}
        return Target("filter", self.target_id(), {**data, "statuses": list(self.statuses)})

    def target_id(self) -> str:
        parts = []
        if self.teams:
            parts.append("team=" + "+".join(self.teams))
        if self.cycle:
            parts.append(f"cycle={self.cycle}")
        if self.assignee_me:
            parts.append("assignee=me")
        if self.statuses:
            parts.append("status=" + "+".join(self.statuses))
        return ",".join(parts)

    def restart(self) -> str:
        words = ["linear watch issues"]
        words += [f"--team {t}" for t in self.teams]
        words += [f"--cycle {self.cycle}"] if self.cycle else []
        words += ["--assignee me"] if self.assignee_me else []
        words += [f"--status {shlex.quote(s)}" for s in self.statuses]
        return " ".join(words)

    def issue_filter(self) -> dict[str, Any]:
        """The IssueFilter the server matches every tick: by state name rather than state ids, so a team that adds
        the state later, or renames one to it, is followed without a restart."""
        parts: list[dict[str, Any]] = []
        if len(self.teams) == 1:
            parts.append({"team": {"key": {"eq": self.teams[0]}}})
        elif self.teams:
            parts.append({"team": {"key": {"in": list(self.teams)}}})
        if self.cycle:
            which = {"isActive": {"eq": True}} if self.cycle == "active" else {"number": {"eq": float(self.cycle)}}
            parts.append({"cycle": which})
        if self.assignee_me:
            parts.append({"assignee": {"isMe": {"eq": True}}})
        if self.statuses:
            alternatives = [state_filter(s) for s in self.statuses]
            parts.append(alternatives[0] if len(alternatives) == 1 else {"or": alternatives})
        elif self.assignee_me:
            parts.append({"state": {"type": {"nin": sorted(CLOSED_TYPES)}}})
        return parts[0] if len(parts) == 1 else {"and": parts}

    def outside(
        self, issue: Mapping[str, Any], viewer: str | None, active_cycle: Mapping[str, Any] | None
    ) -> dict[str, Any] | None:
        """Why a compact issue no longer matches (the `issue_left` reason and where it went), or `None` while it
        does. When several parts stop matching at once, the first of status, assignee, team, cycle names it."""
        state = issue.get("state") or {}
        if issue.get("archivedAt"):
            return {"reason": "archived"}
        if not self.status_matches(state):
            return {"reason": "status_changed", "to": state.get("name"), "to_type": state.get("type")}
        assignee = issue.get("assignee") or {}
        if self.assignee_me and (not viewer or assignee.get("id") != viewer):
            return {"reason": "reassigned", "to": assignee.get("name")}
        if self.teams and issue.get("team") not in self.teams:
            return {"reason": "moved", "to": issue.get("team")}
        if self.cycle:
            number = issue.get("cycle")
            wanted = (active_cycle or {}).get("number") if self.cycle == "active" else int(self.cycle)
            if number is None or number != wanted:
                return {"reason": "moved", "to": number}
        return None

    def status_matches(self, state: Mapping[str, Any]) -> bool:
        if not self.statuses:
            return not self.assignee_me or state.get("type") not in CLOSED_TYPES
        name = str(state.get("name") or "").lower()
        return name in self.statuses or (TRIAGE in self.statuses and state.get("type") == TRIAGE)


def state_filter(status: str) -> dict[str, Any]:
    by_name = {"state": {"name": {"eqIgnoreCase": status}}}
    if status == TRIAGE:
        return {"or": [by_name, {"state": {"type": {"eq": TRIAGE}}}]}
    return by_name


def workflow_state_filter(status: str, teams: tuple[str, ...]) -> dict[str, Any]:
    """The WorkflowStateFilter of the start check of one status."""
    by_name: dict[str, Any] = {"name": {"eqIgnoreCase": status}}
    match = {"or": [by_name, {"type": {"eq": TRIAGE}}]} if status == TRIAGE else by_name
    if not teams:
        return match
    return {"and": [match, {"team": {"key": {"in": list(teams)}}}]}
