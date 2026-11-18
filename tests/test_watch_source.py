"""The Linear source against recorded GraphQL answers: no network, the engine's role played by the harness."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from cli_watch_kit.daemon.cache import ByteBoundedCache
from cli_watch_kit.source import NotFound, PollContext, PollItem, RateLimited, Target, Unauthorized
from fake_linear import (
    AFTER,
    BEFORE,
    DOING,
    DONE,
    LATER,
    TODO,
    VIEWER,
    Harness,
    comment,
    connection,
    history,
    issue,
    kinds,
)

from linear_mcp.watch.source import CATALOG


def issue_watch(ident: str) -> Harness:
    return Harness(Target("issue", ident))


class TestIssueWatch:
    def test_the_baseline_reports_nothing_and_remembers_the_issue(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.watch["i0"] = connection(
            [issue("ABC-1", comments=[comment("c-old", "hi", created=BEFORE)], all_comments=["c-old"])]
        )

        outcome = h.poll()

        assert outcome.error is None
        assert kinds(outcome) == []
        assert h.snapshot["issues"]["ABC-1"]["state"]["name"] == "Todo"
        assert h.snapshot["since"] == "2026-01-10T10:00:00.000Z"

    def test_a_state_change_names_who_made_it(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.watch["i0"] = connection([issue("ABC-1")])
        h.poll()
        h.fake.watch["i0"] = connection(
            [issue("ABC-1", state=DOING, updated=AFTER, history=[history(AFTER, toStateId=DOING["id"])])]
        )

        outcome = h.poll()

        assert kinds(outcome) == ["state_changed"]
        data = outcome.events[0].data
        assert data["from"] == "Todo"
        assert data["to"] == "In Progress"
        assert data["to_type"] == "started"
        assert data["actor_is_me"] is True
        assert data["issue"] == "ABC-1"

    def test_the_watch_ends_when_the_issue_is_completed(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.watch["i0"] = connection([issue("ABC-1", state=DOING)])
        h.poll()
        h.fake.watch["i0"] = connection([issue("ABC-1", state=DONE, updated=AFTER)])

        outcome = h.poll()

        assert kinds(outcome) == ["state_changed"]
        assert outcome.ended == "completed"

    def test_an_issue_already_completed_at_the_start_does_not_end_the_watch(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.watch["i0"] = connection([issue("ABC-1", state=DONE)])
        h.poll()

        outcome = h.poll()

        assert outcome.ended is None

    def test_a_missing_issue_is_not_found(self) -> None:
        h = issue_watch("ABC-2")
        h.fake.watch["i0"] = connection([])

        outcome = h.poll()

        assert isinstance(outcome.error, NotFound)
        assert "ABC-2" in str(outcome.error)

    def test_the_baseline_starts_at_linears_time_not_the_local_clock(self) -> None:
        h = issue_watch("ABC-1")
        # The local clock runs an hour ahead; a comment Linear stamps half a minute after the baseline is still new.
        h.clock += 3600
        h.fake.watch["i0"] = connection([issue("ABC-1")])
        h.poll()
        assert h.snapshot["since"] == "2026-01-10T10:00:00.000Z"

        h.fake.watch["i0"] = connection([issue("ABC-1", comments=[comment("c1", "hi")], all_comments=["c1"])])

        assert kinds(h.poll()) == ["comment_created"]

    def test_without_a_date_header_the_baseline_starts_at_the_newest_time_seen(self) -> None:
        h = issue_watch("ABC-1")
        h.source.client._http()  # the shared client is built on first use
        h.fake.watch["i0"] = connection([issue("ABC-1", updated=AFTER)])
        original = h.fake.handler

        def without_date(request: httpx.Request) -> httpx.Response:
            response = original(request)
            del response.headers["date"]
            return response

        h.source.client._transport = httpx.MockTransport(without_date)
        h.source.client._client = None

        h.poll()

        assert h.snapshot["since"] == AFTER

    def test_a_new_comment_an_edit_and_a_reaction(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.watch["i0"] = connection([issue("ABC-1", all_comments=[])])
        h.poll()

        h.fake.watch["i0"] = connection([issue("ABC-1", comments=[comment("c1", "first")], all_comments=["c1"])])
        created = h.poll()
        assert kinds(created) == ["comment_created"]
        assert created.events[0].data["body"] == "first"
        assert created.events[0].data["author"] == "Jane"

        # A reaction moves updatedAt and nothing else.
        reacted = comment("c1", "first", updated=LATER)
        h.fake.watch["i0"] = connection([issue("ABC-1", comments=[reacted], all_comments=["c1"])])
        assert kinds(h.poll()) == []

        edited = comment("c1", "first, fixed", updated=LATER, edited=LATER)
        h.fake.watch["i0"] = connection([issue("ABC-1", comments=[edited], all_comments=["c1"])])
        assert kinds(h.poll()) == ["comment_edited"]

    def test_a_comment_from_before_the_watch_is_not_new(self) -> None:
        h = issue_watch("ABC-1")
        old = comment("c-old", "old", created="2026-01-10T09:59:00.000Z")
        h.fake.watch["i0"] = connection([issue("ABC-1", comments=[old], all_comments=["c-old"])])
        h.poll()
        reacted = comment("c-old", "old", created="2026-01-10T09:59:00.000Z", updated=AFTER)
        h.fake.watch["i0"] = connection([issue("ABC-1", comments=[reacted], all_comments=["c-old"])])

        assert kinds(h.poll()) == []

    def test_resolving_and_deleting_comments(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.watch["i0"] = connection([issue("ABC-1", all_comments=["c-gone"])])
        h.poll()
        h.fake.watch["i0"] = connection([issue("ABC-1", comments=[comment("c1", "q")], all_comments=["c1", "c-gone"])])
        h.poll()

        resolved = comment("c1", "q", updated=LATER, resolved=LATER)
        h.fake.watch["i0"] = connection([issue("ABC-1", comments=[resolved], all_comments=["c1"])])
        outcome = h.poll()

        assert kinds(outcome) == ["comment_resolved", "comment_deleted"]
        assert outcome.events[1].data["comment_id"] == "c-gone"


class TestFailures:
    def test_a_429_blocks_with_its_retry_after(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.fail = (429, {"retry-after": "42"}, {"errors": [{"message": "Too many requests"}]})

        with pytest.raises(RateLimited) as raised:
            h.poll()

        assert raised.value.retry_after == 42.0

    def test_a_graphql_rate_limit_error_is_a_rate_limit(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.fail = (400, {}, {"errors": [{"message": "limited", "extensions": {"code": "RATELIMITED"}}]})

        with pytest.raises(RateLimited):
            h.poll()

    def test_a_refused_key_is_unauthorized(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.fail = (400, {}, {"errors": [{"message": "bad key", "extensions": {"code": "AUTHENTICATION_ERROR"}}]})

        with pytest.raises(Unauthorized):
            h.poll()

    def test_the_readings_reach_the_budget_and_the_complexity_is_charged(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.watch["i0"] = connection([issue("ABC-1")])

        h.poll()

        described = h.budget.describe(h.clock)["dimensions"]
        assert described["requests"]["remaining"] == 2400
        assert described["complexity"]["remaining"] == 2900000
        assert h.source.status()["last_complexity"] == 42


class TestTeamWatch:
    def team(self) -> Harness:
        h = Harness(Target("team", "ABC"))
        h.fake.watch["t0"] = {"id": "team-ABC", "key": "ABC", "activeCycle": None}
        h.fake.pages = [issue("ABC-1"), issue("ABC-2", assignee="Jane")]
        assert kinds(h.poll()) == []
        assert sorted(h.snapshot["members"]) == ["uuid-ABC-1", "uuid-ABC-2"]
        return h

    def test_a_new_comment_without_an_issue_update(self) -> None:
        h = self.team()
        # The issue's updatedAt stays before the watch; only the comment is new.
        h.fake.watch["k0"] = connection([issue("ABC-1", comments=[comment("c1", "hello")])])
        h.fake.watch["e0"] = connection([])

        outcome = h.poll()

        assert kinds(outcome) == ["comment_created"]
        assert outcome.events[0].data["issue"] == "ABC-1"

    def test_issues_enter_and_leave(self) -> None:
        h = self.team()
        h.fake.watch["k0"] = connection([issue("ABC-2", team="XYZ", updated=AFTER, assignee="Jane")])
        h.fake.watch["e0"] = connection([issue("ABC-3", created=AFTER, updated=AFTER)])

        outcome = h.poll()

        assert kinds(outcome) == ["issue_left", "issue_entered"]
        assert outcome.events[0].data["issue"] == "ABC-2"
        assert outcome.events[1].data["issue"] == "ABC-3"
        assert sorted(h.snapshot["members"]) == ["uuid-ABC-1", "uuid-ABC-3"]

    def test_an_old_closed_issue_that_was_touched_does_not_enter(self) -> None:
        h = self.team()
        h.fake.watch["k0"] = connection([])
        h.fake.watch["e0"] = connection([issue("ABC-9", state=DONE, updated=AFTER)])

        outcome = h.poll()

        assert kinds(outcome) == []
        assert "uuid-ABC-9" in h.snapshot["members"]

    def test_one_request_per_tick_when_nothing_is_due_for_a_relist(self) -> None:
        h = self.team()
        h.fake.requests.clear()
        h.fake.watch["k0"] = connection([])
        h.fake.watch["e0"] = connection([])

        h.poll()

        assert len(h.fake.requests) == 1


class TestCycleWatch:
    def test_the_rollover_reports_the_new_cycle_and_the_issues_left_behind(self) -> None:
        h = Harness(Target("cycle", "ABC/active"))
        h.fake.watch["t0"] = {"id": "team-ABC", "key": "ABC", "activeCycle": {"id": "cycle-5", "number": 5}}
        h.fake.pages = [issue("ABC-1", state=DONE, cycle=5), issue("ABC-2", cycle=5)]
        h.poll()
        assert sorted(h.snapshot["members"]) == ["uuid-ABC-1", "uuid-ABC-2"]

        h.fake.watch["t0"] = {"id": "team-ABC", "key": "ABC", "activeCycle": {"id": "cycle-6", "number": 6}}
        # The open issue moved to the new cycle; the completed one stays behind, untouched.
        h.fake.watch["k0"] = connection([issue("ABC-2", cycle=6, updated=AFTER)])
        h.fake.watch["e0"] = connection([])
        h.fake.ids = ["uuid-ABC-2"]

        outcome = h.poll()

        assert kinds(outcome) == ["active_cycle_changed", "cycle_changed", "issue_left"]
        assert outcome.events[0].data == {"team": "ABC", "from": 5, "to": 6}
        assert outcome.events[2].data["issue"] == "ABC-1"
        assert h.snapshot["active_cycle"]["number"] == 6


class TestViewWatch:
    def test_membership_comes_from_the_view_and_a_candidate_triggers_a_relist(self) -> None:
        h = Harness(Target("view", "0123456789ab"))
        h.fake.watch["v0"] = {
            "id": "view-1",
            "slugId": "0123456789ab",
            "updatedAt": "2026-01-01T00:00:00.000Z",
            "filterData": {"state": {"type": {"eq": "started"}}},
            "team": {"id": "team-ABC", "key": "ABC"},
        }
        h.fake.view_ids = ["uuid-ABC-1"]
        h.fake.pages = [issue("ABC-1", state=DOING)]
        h.poll()
        assert list(h.snapshot["members"]) == ["uuid-ABC-1"]

        h.fake.watch["k0"] = connection([])
        h.fake.watch["e0"] = connection([issue("ABC-4", state=DOING, updated=AFTER)])
        h.fake.view_ids = ["uuid-ABC-1", "uuid-ABC-4"]
        h.fake.pages = [issue("ABC-1", state=DOING), issue("ABC-4", state=DOING, updated=AFTER)]

        outcome = h.poll()

        assert kinds(outcome) == ["issue_entered"]
        assert outcome.events[0].data["issue"] == "ABC-4"

    def test_a_missing_view_is_not_found(self) -> None:
        h = Harness(Target("view", "0123456789ab"))
        h.fake.watch["v0"] = None

        outcome = h.poll()

        assert isinstance(outcome.error, NotFound)


def test_two_targets_share_one_request() -> None:
    h = issue_watch("ABC-1")
    h.fake.watch["i0"] = connection([issue("ABC-1")])
    h.fake.watch["i1"] = connection([issue("ABC-2")])
    other = Target("issue", "ABC-2")
    ctx = PollContext(VIEWER, {"api_key": "k"}, h.budget, ByteBoundedCache())
    items: list[PollItem[Any]] = [PollItem(h.target, None, frozenset()), PollItem(other, None, frozenset())]

    outcomes = asyncio.run(h.source.poll(items, ctx))

    assert len(h.fake.requests) == 1
    assert all(o.error is None for o in outcomes.values())
    assert TODO["name"] == outcomes["issue ABC-2"].snapshot["issues"]["ABC-2"]["state"]["name"]  # type: ignore[index]


class TestDiffForResubscribers:
    def test_an_issue_baseline_against_the_current_snapshot(self) -> None:
        h = issue_watch("ABC-1")
        h.fake.watch["i0"] = connection([issue("ABC-1", all_comments=["c-gone"])])
        h.poll()
        baseline = h.snapshot
        h.fake.watch["i0"] = connection([issue("ABC-1", state=DOING, updated=AFTER, all_comments=["c-new"])])
        h.poll()

        events = h.source.diff(h.target, baseline, h.snapshot, frozenset({"state_changed", "comment_created"}))

        assert [e.kind for e in events] == ["state_changed", "comment_created"]
        assert events[0].data["actor"] is None
        assert events[1].data["comment_id"] == "c-new"

    def test_a_team_baseline_reports_who_entered_and_left(self) -> None:
        h = Harness(Target("team", "ABC"))
        h.fake.watch["t0"] = {"id": "team-ABC", "key": "ABC", "activeCycle": None}
        h.fake.pages = [issue("ABC-1"), issue("ABC-2")]
        h.poll()
        baseline = h.snapshot
        current = {**baseline, "members": {k: v for k, v in baseline["members"].items() if k != "uuid-ABC-2"}}
        current["members"]["uuid-ABC-3"] = {
            **baseline["members"]["uuid-ABC-1"],
            "id": "uuid-ABC-3",
            "identifier": "ABC-3",
        }

        events = h.source.diff(h.target, baseline, current, frozenset(CATALOG.produced("team")))

        assert [(e.kind, e.data["issue"]) for e in events] == [("issue_entered", "ABC-3"), ("issue_left", "ABC-2")]
