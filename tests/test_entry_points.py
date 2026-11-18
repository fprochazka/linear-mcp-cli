"""`linear mcp ...` and `linear-mcp ...` behave the same, and `linear` loads the MCP side only when `mcp` is used."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from importlib.metadata import version
from pathlib import Path

import pytest
from fixture_server import MISSING_ISSUE, RunningServer, start

from linear_mcp import DISTRIBUTION
from linear_mcp.cli import main, mcp_main

KEY = "lin_api_" + "y" * 32

EntryPoint = Callable[[Sequence[str] | None], None]


@pytest.fixture(scope="module")
def linear_server() -> Iterator[RunningServer]:
    server = start()
    yield server
    server.stop()


@pytest.fixture
def server(linear_server: RunningServer, monkeypatch: pytest.MonkeyPatch, home: Path) -> RunningServer:
    """The fixture server in place of Linear's, with the tool list already in the cache."""
    monkeypatch.setenv("LINEAR_MCP_SERVERS__LINEAR__URL", linear_server.url)
    monkeypatch.setenv("LINEAR_API_KEY", KEY)
    with pytest.raises(SystemExit):
        mcp_main(["--help"])
    assert (home / ".cache" / "linear-mcp" / "linear.json").exists()
    linear_server.recorder.reset()
    return linear_server


def run(entry: EntryPoint, args: Sequence[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    capsys.readouterr()
    with pytest.raises(SystemExit) as exited:
        entry(args)
    captured = capsys.readouterr()
    code = exited.value.code
    return code if isinstance(code, int) else 1, captured.out, captured.err


def same_program(text: str) -> str:
    """Spell the program name one way, so the output of both entry points compares."""
    return text.replace("linear mcp", "linear-mcp")


CASES = {
    "help": (["--help"], 0),
    "config": (["config"], 0),
    "schema": (["schema", "get-issue"], 0),
    "tool-call": (["get-issue", "--id", "ABC-1", "--include-relations"], 0),
    "unknown-command": (["nosuch"], 2),
    "tool-error": (["get-issue", "--id", MISSING_ISSUE], 1),
}


@pytest.mark.parametrize(("args", "expected_code"), CASES.values(), ids=CASES.keys())
def test_linear_mcp_is_the_same_as_linear_mcp_subcommand(
    server: RunningServer, capsys: pytest.CaptureFixture[str], args: list[str], expected_code: int
) -> None:
    sub = run(main, ["mcp", *args], capsys)
    sub_calls = list(server.recorder.calls)
    server.recorder.reset()
    alias = run(mcp_main, args, capsys)

    assert sub[0] == alias[0] == expected_code, sub[2] + alias[2]
    assert same_program(sub[1]) == same_program(alias[1])
    assert same_program(sub[2]) == same_program(alias[2])
    assert sub_calls == server.recorder.calls
    assert KEY not in sub[1] + sub[2]


def test_the_tools_are_listed_from_the_cache(server: RunningServer, capsys: pytest.CaptureFixture[str]) -> None:
    code, stdout, _ = run(main, ["mcp", "--help"], capsys)

    assert code == 0
    assert "Usage: linear mcp [OPTIONS] COMMAND [ARGS]..." in stdout
    assert "get-issue" in stdout
    assert "list-teams" in stdout
    assert server.recorder.methods == []


def test_a_tool_call_reaches_the_server(server: RunningServer, capsys: pytest.CaptureFixture[str]) -> None:
    code, stdout, _ = run(main, ["mcp", "get-issue", "--id", "ABC-1", "--json"], capsys)

    assert code == 0
    assert json.loads(stdout) == {"identifier": "ABC-1", "title": "Fix the login", "relations": False}
    assert server.recorder.calls == [{"name": "get_issue", "arguments": {"id": "ABC-1"}}]


@pytest.mark.parametrize(
    ("entry", "prefix", "hint"),
    [(main, ["mcp"], "Run 'linear mcp --help'"), (mcp_main, [], "Run 'linear-mcp --help'")],
    ids=["linear", "linear-mcp"],
)
def test_hints_name_the_command_that_was_typed(
    server: RunningServer, capsys: pytest.CaptureFixture[str], entry: EntryPoint, prefix: list[str], hint: str
) -> None:
    code, _, stderr = run(entry, [*prefix, "nosuch"], capsys)

    assert code == 2
    assert hint in stderr


def test_linear_shows_its_version(capsys: pytest.CaptureFixture[str]) -> None:
    code, stdout, _ = run(main, ["--version"], capsys)

    assert code == 0
    assert stdout == f"linear {version(DISTRIBUTION)}\n"


def test_linear_mcp_shows_its_version(capsys: pytest.CaptureFixture[str]) -> None:
    code, stdout, _ = run(mcp_main, ["--version"], capsys)

    assert code == 0
    assert stdout.startswith(f"linear-mcp {version(DISTRIBUTION)} (mcp-to-cli-kit ")


HEAVY_MODULES = ("mcp", "httpx", "pydantic", "jsonschema", "anyio", "yaml", "cc_blackbox", "mcp_to_cli_kit.cli")

LAZY_SCRIPT = """
import json, sys
from linear_mcp.cli import main
try:
    main({args!r})
except SystemExit as exited:
    code = exited.code
loaded = [name for name in {heavy!r} if name in sys.modules]
print(json.dumps({{"code": code, "loaded": loaded}}), file=sys.stderr)
"""


@pytest.mark.parametrize(
    ("args", "listed"),
    [
        (
            ["--help"],
            ["mcp    Call the tools of Linear's MCP server.", "watch  Follow issues, views, teams and cycles"],
        ),
        (
            ["watch", "--help"],
            ["daemon  Inspect or stop", "issue   Watch one issue", "issues  Watch the issues"],
        ),
        (["watch", "issues", "--help"], ["--view TEXT", "--team TEXT", "--cycle TEXT", "--no-daemon"]),
    ],
    ids=["linear", "watch", "watch-issues"],
)
def test_help_loads_nothing_of_the_mcp_or_http_side(tmp_path: Path, args: list[str], listed: list[str]) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "XDG_CACHE_HOME": str(cache),
        # Any request would fail on this closed port.
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "HTTP_PROXY": "http://127.0.0.1:9",
    }

    completed = subprocess.run(
        [sys.executable, "-c", LAZY_SCRIPT.format(args=args, heavy=HEAVY_MODULES)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    result = json.loads(completed.stderr.strip().splitlines()[-1])
    assert result == {"code": 0, "loaded": []}
    for line in listed:
        assert line in completed.stdout
    assert list(cache.iterdir()) == []
