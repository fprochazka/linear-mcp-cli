"""Parsing what `linear watch` is given, and where it finds the API key."""

from __future__ import annotations

from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from linear_mcp.cli import linear_group
from linear_mcp.watch.cli import issue_ref, view_ref
from linear_mcp.watch.credentials import MissingKey, api_key

KEY = "lin_api_" + "z" * 32


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("abc-123", "ABC-123"),
        ("https://linear.app/example/issue/ABC-123/fix-the-login", "ABC-123"),
        ("https://linear.app/example/issue/ABC-123", "ABC-123"),
        ("6F5A1E2B-1C3D-4E5F-8A9B-0C1D2E3F4A5B", "6f5a1e2b-1c3d-4e5f-8a9b-0c1d2e3f4a5b"),
    ],
)
def test_issue_refs(value: str, expected: str) -> None:
    assert issue_ref(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0123456789ab", "0123456789ab"),
        ("https://linear.app/example/view/my-open-bugs-0123456789ab", "0123456789ab"),
        ("https://linear.app/example/view/0123456789AB/", "0123456789ab"),
    ],
)
def test_view_refs(value: str, expected: str) -> None:
    assert view_ref(value) == expected


@pytest.mark.parametrize("value", ["ABC", "issue 12", "https://linear.app/example/project/x"])
def test_bad_refs(value: str) -> None:
    with pytest.raises(click.BadParameter):
        issue_ref(value)
    with pytest.raises(click.BadParameter):
        view_ref(value)


def test_the_config_file_wins_over_the_variable_and_bearer_is_stripped(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("servers:\n  linear:\n    headers:\n      Authorization: Bearer from-file\n", encoding="utf-8")

    assert api_key(config, {"LINEAR_API_KEY": KEY}) == "from-file"
    # No file at the default path: the variable.
    assert api_key(None, {"LINEAR_API_KEY": KEY}) == KEY


def test_without_a_key_the_variable_is_named(home: Path) -> None:
    with pytest.raises(MissingKey, match="LINEAR_API_KEY"):
        api_key(None, {})


def test_a_config_file_that_does_not_exist_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(MissingKey, match="does not exist"):
        api_key(tmp_path / "missing.yaml", {"LINEAR_API_KEY": KEY})


def test_a_missing_key_is_a_usage_error_before_anything_is_contacted(home: Path) -> None:
    result = CliRunner().invoke(linear_group(), ["watch", "issue", "ABC-1", "--no-daemon"])

    assert result.exit_code == 2
    assert "LINEAR_API_KEY, which is not set" in result.stderr


def test_watch_issues_needs_exactly_one_scope() -> None:
    result = CliRunner().invoke(linear_group(), ["watch", "issues", "--cycle", "active"])

    assert result.exit_code == 2
    assert "exactly one of --view and --team" in result.stderr
