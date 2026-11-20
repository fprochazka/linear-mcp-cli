"""`linear watch issues --assignee me` and `--status`: the filter target against recorded GraphQL answers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from cli_watch_kit.source import Target
from fake_linear import (
    AFTER,
    BACKLOG,
    DECLINED,
    DOING,
    DONE,
    TODO,
    TRIAGE,
    FakeLinear,
    Harness,
    connection,
    history,
    issue,
    kinds,
)

from linear_mcp.watch.cli import check_filter
from linear_mcp.watch.files import resource_dir
from linear_mcp.watch.filters import FilterSpec
from linear_mcp.watch.source import CATALOG

JANE = "user-Jane"


def watch(spec: FilterSpec, pages: list[dict[str, Any]]) -> Harness:
    """A filter watch after its silent baseline of `pages`."""
    h = Harness(spec.target())
    h.fake.ids = [p["id"] for p in pages]
    h.fake.pages = pages
    assert kinds(h.poll()) == []
    assert sorted(h.snapshot["members"]) == sorted(p["id"] for p in pages)
    assert h.snapshot["since"] == "2026-01-10T10:00:00.000Z"
    return h


def tick(h: Harness, known: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> Any:
    h.fake.watch["k0"] = connection(known)
    h.fake.watch["e0"] = connection(candidates)
    return h.poll()


MINE = FilterSpec.of(assignee_me=True)
TRIAGE_OF_ABC = FilterSpec.of(("ABC",), statuses=("Triage",))


class TestTarget:
    def test_the_same_filter_in_another_order_is_the_same_target(self) -> None:
        a = FilterSpec.of(("def", "ABC"), None, True, ("In Progress", "backlog")).target()
        b = FilterSpec.of(("ABC", "DEF", "abc"), None, True, ("Backlog", "in progress ")).target()

        assert a == b
        assert a.key == "filter team=ABC+DEF,assignee=me,status=backlog+in progress"
        assert FilterSpec.from_target(Target.from_wire(a.to_wire())) == FilterSpec.from_target(b)

    def test_the_restart_line_spells_out_every_part(self) -> None:
        spec = FilterSpec.of(("ABC",), "active", False, ("In Progress", "Backlog"))

        assert spec.restart() == "linear watch issues --team ABC --cycle active --status backlog --status 'in progress'"

    def test_the_server_filter_is_the_and_of_the_parts(self) -> None:
        assert MINE.issue_filter() == {
            "and": [{"assignee": {"isMe": {"eq": True}}}, {"state": {"type": {"nin": ["canceled", "completed"]}}}]
        }
        assert FilterSpec.of(("ABC", "DEF"), statuses=("Backlog", "Todo")).issue_filter() == {
            "and": [
                {"team": {"key": {"in": ["ABC", "DEF"]}}},
                {
                    "or": [
                        {"state": {"name": {"eqIgnoreCase": "backlog"}}},
                        {"state": {"name": {"eqIgnoreCase": "todo"}}},
                    ]
                },
            ]
        }
        # Triage also by type, so a renamed triage state still matches.
        assert FilterSpec.of(statuses=("TRIAGE",)).issue_filter() == {
            "or": [{"state": {"name": {"eqIgnoreCase": "triage"}}}, {"state": {"type": {"eq": "triage"}}}]
        }

    def test_a_renamed_triage_state_still_matches_locally(self) -> None:
        spec = FilterSpec.of(statuses=("triage",))
        inbox = {"state": {"id": "s", "name": "Inbox", "type": "triage"}, "team": "ABC"}

        assert spec.outside(inbox, None, None) is None
        assert FilterSpec.of(statuses=("backlog",)).outside(inbox, None, None) == {
            "reason": "status_changed",
            "to": "Inbox",
            "to_type": "triage",
        }

    def test_the_resource_dir_is_under_filters(self) -> None:
        place = resource_dir("example")
        assert place(Path("/b"), MINE.target()) == Path("/b/example/filters/assignee-me")
        assert place(Path("/b"), TRIAGE_OF_ABC.target()) == Path("/b/example/filters/team-ABC-status-triage")


class TestAssignedToMe:
    def test_an_issue_created_already_assigned_to_me_enters_as_created(self) -> None:
        h = watch(MINE, [issue("ABC-1", assignee="me")])
        new = issue("ABC-2", assignee="me", created=AFTER, updated=AFTER, creator="Jane")

        outcome = tick(h, [], [new])

        assert kinds(outcome) == ["issue_entered"]
        data = outcome.events[0].data
        assert data["reason"] == "created"
        assert data["actor"] == "Jane"
        assert data["actor_is_me"] is False
        assert data["team"] == "ABC"
        assert data["priority"] == 3
        assert data["created_at"] == AFTER

    def test_an_issue_reassigned_to_me_names_who_and_from_whom(self) -> None:
        h = watch(MINE, [])
        row = history(AFTER, actor=JANE, toAssigneeId="user-me", fromAssignee={"id": "user-Bob", "name": "Bob"})
        moved = issue("ABC-3", assignee="me", updated=AFTER, history=[row])

        outcome = tick(h, [], [moved])

        assert kinds(outcome) == ["issue_entered"]
        data = outcome.events[0].data
        assert (data["reason"], data["from"], data["actor"], data["actor_is_me"]) == ("assigned", "Bob", "Jane", False)

    def test_a_self_assignment_is_reported_as_mine(self) -> None:
        h = watch(MINE, [])
        row = history(AFTER, toAssigneeId="user-me", fromAssignee=None)
        taken = issue("ABC-4", assignee="me", updated=AFTER, history=[row])

        data = tick(h, [], [taken]).events[0].data

        assert (data["reason"], data["from"], data["actor_is_me"]) == ("assigned", None, True)

    def test_a_reopened_issue_enters_as_a_status_change(self) -> None:
        h = watch(MINE, [])
        row = history(AFTER, actor=JANE, toStateId=TODO["id"], fromState={"name": "Done", "type": "completed"})
        reopened = issue("ABC-5", assignee="me", updated=AFTER, history=[row])

        data = tick(h, [], [reopened]).events[0].data

        assert (data["reason"], data["from_state"], data["from_type"]) == ("status_changed", "Done", "completed")

    def test_an_entry_before_its_history_row_has_no_reason_and_no_actor(self) -> None:
        h = watch(MINE, [])

        data = tick(h, [], [issue("ABC-6", assignee="me", updated=AFTER)]).events[0].data

        assert (data["reason"], data["actor"], data["actor_is_me"]) == (None, None, False)

    def test_reassigned_away_and_completed_issues_leave(self) -> None:
        h = watch(MINE, [issue("ABC-1", assignee="me"), issue("ABC-2", assignee="me", state=DOING)])
        away = issue("ABC-1", assignee="Jane", updated=AFTER, history=[history(AFTER, toAssigneeId=JANE)])
        done = issue("ABC-2", assignee="me", state=DONE, updated=AFTER, history=[history(AFTER, toStateId=DONE["id"])])

        outcome = tick(h, [away, done], [])

        assert kinds(outcome) == ["assignee_changed", "issue_left", "state_changed", "issue_left"]
        left = [e.data for e in outcome.events if e.kind == "issue_left"]
        assert (left[0]["reason"], left[0]["to"]) == ("reassigned", "Jane")
        assert (left[1]["reason"], left[1]["to"], left[1]["to_type"]) == ("status_changed", "Done", "completed")
        assert h.snapshot["members"] == {}

    def test_a_member_that_changes_and_still_matches_stays(self) -> None:
        h = watch(MINE, [issue("ABC-1", assignee="me")])

        outcome = tick(h, [issue("ABC-1", assignee="me", state=DOING, updated=AFTER)], [])

        assert kinds(outcome) == ["state_changed"]
        assert "uuid-ABC-1" in h.snapshot["members"]

    def test_the_candidates_ask_for_who_created_and_moved_them(self) -> None:
        h = watch(MINE, [issue("ABC-1", assignee="me")])
        h.fake.requests.clear()

        tick(h, [], [])

        (request,) = h.fake.requests
        assert "e0: issues(" in request["query"] and "...E " in request["query"] and "...HE " in request["query"]
        assert request["variables"]["c0"]["and"][0] == MINE.issue_filter()


class TestTriage:
    def test_an_issue_created_into_triage_by_a_bot(self) -> None:
        h = watch(TRIAGE_OF_ABC, [issue("ABC-1", state=TRIAGE)])
        new = issue("ABC-7", state=TRIAGE, created=AFTER, updated=AFTER, bot="Slack")

        data = tick(h, [], [new]).events[0].data

        assert (data["reason"], data["actor"], data["actor_is_me"], data["state"]) == (
            "created",
            "Slack (bot)",
            False,
            "Triage",
        )

    def test_an_issue_moved_in_from_another_team(self) -> None:
        h = watch(TRIAGE_OF_ABC, [])
        row = history(AFTER, actor=JANE, toTeamId="team-ABC", fromTeam={"key": "DEF"}, toStateId=TRIAGE["id"])
        moved = issue("ABC-8", state=TRIAGE, updated=AFTER, history=[row])

        data = tick(h, [], [moved]).events[0].data

        assert (data["reason"], data["from_team"], data["actor"]) == ("moved", "DEF", "Jane")

    def test_accepted_and_declined_issues_leave_with_where_they_went(self) -> None:
        h = watch(TRIAGE_OF_ABC, [issue("ABC-1", state=TRIAGE), issue("ABC-2", state=TRIAGE)])
        accepted = issue("ABC-1", state=BACKLOG, updated=AFTER)
        declined = issue("ABC-2", state=DECLINED, updated=AFTER)

        outcome = tick(h, [accepted, declined], [])

        left = [
            (e.data["issue"], e.data["reason"], e.data["to"], e.data["to_type"])
            for e in outcome.events
            if e.kind == "issue_left"
        ]
        assert left == [
            ("ABC-1", "status_changed", "Backlog", "backlog"),
            ("ABC-2", "status_changed", "Declined", "canceled"),
        ]

    def test_a_team_less_filter_reads_no_team_and_still_starts_at_linears_time(self) -> None:
        h = Harness(FilterSpec.of(statuses=("triage",)).target())

        h.poll()

        watch_request = next(r for r in h.fake.requests if "query Watch" in r["query"])
        assert "team(" not in watch_request["query"]
        assert h.snapshot == {"members": {}, "comments": {}, "since": "2026-01-10T10:00:00.000Z"}

    def test_two_statuses_are_either(self) -> None:
        spec = FilterSpec.of(("ABC",), statuses=("Triage", "Backlog"))
        h = watch(spec, [issue("ABC-1", state=TRIAGE)])

        outcome = tick(h, [issue("ABC-1", state=BACKLOG, updated=AFTER)], [])

        assert kinds(outcome) == ["state_changed"]
        assert "uuid-ABC-1" in h.snapshot["members"]


class TestCap:
    def test_a_filter_above_2000_issues_ends_at_its_first_poll(self) -> None:
        h = Harness(FilterSpec.of(statuses=("done",)).target())
        h.fake.ids = [f"uuid-{n}" for n in range(2001)]

        outcome = h.poll()

        assert outcome.ended == "too_large"
        assert outcome.snapshot is None
        assert outcome.end_data["issues"] == 2001
        assert "--team, --assignee me or --cycle" in outcome.end_data["message"]
        assert not any("query Page" in r["query"] for r in h.fake.requests)

    def test_a_relist_finds_what_left_without_a_change(self) -> None:
        h = watch(MINE, [issue("ABC-1", assignee="me"), issue("ABC-2", assignee="me")])
        h.clock += 601
        h.fake.ids = ["uuid-ABC-1"]

        outcome = tick(h, [], [])

        assert [(e.kind, e.data["issue"], e.data["reason"]) for e in outcome.events] == [
            ("issue_left", "ABC-2", "relisted")
        ]


def test_a_resubscriber_learns_who_entered_and_left_in_the_gap() -> None:
    h = watch(MINE, [issue("ABC-1", assignee="me"), issue("ABC-2", assignee="me")])
    baseline = h.snapshot
    tick(h, [issue("ABC-2", assignee="Jane", updated=AFTER)], [issue("ABC-3", assignee="me", updated=AFTER)])

    events = h.source.diff(h.target, baseline, h.snapshot, frozenset(CATALOG.produced("filter")))

    assert [(e.kind, e.data["issue"]) for e in events] == [("issue_entered", "ABC-3"), ("issue_left", "ABC-2")]


class TestStartCheck:
    def check(self, spec: FilterSpec, answer: dict[str, Any]) -> list[str]:
        self.fake = FakeLinear(check=answer)
        with httpx.Client(transport=httpx.MockTransport(self.fake.handler)) as client:
            return check_filter("lin_api_test", spec, client)

    @property
    def request(self) -> dict[str, Any]:
        (request,) = self.fake.requests
        return request

    def test_the_header_says_in_how_many_teams_a_status_exists(self) -> None:
        answer = {"s0": connection([{"team": {"key": "ABC"}}, {"team": {"key": "DEF"}}])}

        assert self.check(FilterSpec.of(statuses=("Triage",)), answer) == ["status: triage (2 teams)"]
        assert self.request["variables"]["s0"] == {
            "or": [{"name": {"eqIgnoreCase": "triage"}}, {"type": {"eq": "triage"}}]
        }

    def test_an_unknown_status_in_any_team_is_a_usage_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exited:
            self.check(FilterSpec.of(statuses=("Triag",)), {"s0": connection([])})

        assert exited.value.code == 2
        assert "no workflow state named 'triag' in any team you can read" in capsys.readouterr().err

    def test_an_unknown_status_of_a_team_lists_its_states(self, capsys: pytest.CaptureFixture[str]) -> None:
        states = {"nodes": [{"name": "Todo"}, {"name": "Backlog"}]}
        answer = {"teams": connection([{"key": "ABC", "states": states}]), "s0": connection([])}

        with pytest.raises(SystemExit) as exited:
            self.check(FilterSpec.of(("ABC",), statuses=("Triag",)), answer)

        assert exited.value.code == 2
        assert "no workflow state named 'triag' in team ABC; its states: Backlog, Todo" in capsys.readouterr().err
        assert self.request["variables"]["s0"]["and"][1] == {"team": {"key": {"in": ["ABC"]}}}

    def test_an_unknown_team_is_a_usage_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exited:
            self.check(FilterSpec.of(("XYZ",), assignee_me=True), {"teams": connection([])})

        assert exited.value.code == 2
        assert "no team XYZ" in capsys.readouterr().err

    def test_my_issues_alone_need_no_check(self) -> None:
        assert check_filter("lin_api_test", MINE, None) == []
