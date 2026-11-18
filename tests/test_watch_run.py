"""`linear watch issue` end to end with `--no-daemon` and stdout, over the recorded GraphQL endpoint."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner
from fake_linear import AFTER, DONE, FakeLinear, connection, history, issue

from linear_mcp.cli import linear_group
from linear_mcp.watch import cli as watch_cli
from linear_mcp.watch import source as source_module
from linear_mcp.watch.app import APP
from linear_mcp.watch.graphql import LinearGraphQL
from linear_mcp.watch.source import LinearSource


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeLinear:
    fake = FakeLinear()
    source = LinearSource(LinearGraphQL(transport=httpx.MockTransport(fake.handler)))
    source.coalesce_window = 0.1  # the first poll waits this long for others to share it
    monkeypatch.setattr(watch_cli, "APP", APP.with_overrides(source=source, client_poll_ms=50))
    monkeypatch.setattr(source_module, "ISSUE_INTERVAL", 0.5)
    # The workspace lookup before the watch starts; the watch itself goes through the fake.
    monkeypatch.setattr(watch_cli, "resolve", lambda config_path: ("lin_api_test", "example"))
    return fake


def test_an_issue_watch_reports_a_change_and_ends_when_the_issue_is_done(fake: FakeLinear, tmp_path: Path) -> None:
    done = issue("ABC-1", state=DONE, updated=AFTER, history=[history(AFTER, toStateId=DONE["id"])])
    fake.script = [{"i0": connection([issue("ABC-1")])}, {"i0": connection([done])}]

    result = CliRunner().invoke(
        linear_group(),
        [
            "watch",
            "issue",
            "abc-1",
            "--no-daemon",
            "--events-stream",
            "stdout",
            "--base-dir",
            str(tmp_path),
            "--timeout",
            "30s",
        ],
    )

    assert result.exit_code == 0, result.stderr
    header = result.stderr.splitlines()
    assert header[0] == "linear watch: resource: issue ABC-1"
    assert "linear watch: stream: stdout (one JSON event per line)" in header
    assert f"linear watch: dir: {tmp_path / 'example' / 'issues' / 'ABC-1'}" in header
    assert "linear watch: workspace: example" in header
    assert "linear watch: daemon: in-process (--no-daemon), private budget" in header
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert [e["kind"] for e in events] == ["watch_started", "state_changed", "watch_ended"]
    assert events[1]["data"]["to"] == "Done"
    assert events[1]["data"]["actor_is_me"] is True
    assert events[2]["data"]["reason"] == "completed"
    changelog = tmp_path / "example" / "issues" / "ABC-1" / "events.jsonl"
    assert [json.loads(line)["kind"] for line in changelog.read_text().splitlines()] == [e["kind"] for e in events]
