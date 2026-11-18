"""`linear watch issue|issues|daemon`, on cli-watch-kit. Imported only when `linear watch` is used."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
from cli_watch_kit.cli import WatchOptions, daemon_group, run_watch, watch_options
from cli_watch_kit.source import Target

from linear_mcp.watch.app import APP
from linear_mcp.watch.credentials import MissingKey, api_key
from linear_mcp.watch.files import README, LinearWriter, resource_dir

EXIT_USAGE = 2
ISSUE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*-\d+$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
SLUG = re.compile(r"^[0-9a-f]{12}$", re.IGNORECASE)

CONFIG_OPTION = click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="The linear-mcp config file to read the API key from, when LINEAR_API_KEY is not set.",
)


def issue_ref(value: str) -> str:
    """`ABC-123`, a UUID, or an issue URL (`https://linear.app/<ws>/issue/ABC-123/...`)."""
    match = re.search(r"/issue/([A-Za-z][A-Za-z0-9_]*-\d+)", value)
    ref = match.group(1) if match else value.strip()
    if ISSUE_ID.match(ref):
        return ref.upper()
    if UUID.match(ref):
        return ref.lower()
    raise click.BadParameter(f"{value!r} is not an issue identifier (ABC-123), UUID or issue URL")


def view_ref(value: str) -> str:
    """A view's slugId (12 hex), its UUID, or its URL (`https://linear.app/<ws>/view/<name>-<slugId>`)."""
    match = re.search(r"/view/(?:[^/?#]*-)?([0-9a-f]{12})(?:[/?#]|$)", value, re.IGNORECASE)
    ref = match.group(1) if match else value.strip()
    if SLUG.match(ref) or UUID.match(ref):
        return ref.lower()
    raise click.BadParameter(f"{value!r} is not a view slugId, UUID or view URL")


def resolve(config_path: Path | None) -> tuple[str, str]:
    """The API key and the workspace's URL key; exits with a usage error when the key is missing or refused."""
    try:
        key = api_key(config_path)
    except MissingKey as exc:
        click.echo(f"{APP.status_prefix}error: {exc}", err=True)
        sys.exit(EXIT_USAGE)
    import httpx

    from linear_mcp.watch.graphql import API_URL, USER_AGENT
    from linear_mcp.watch.queries import VIEWER

    try:
        response = httpx.post(
            API_URL, json={"query": VIEWER}, headers={"Authorization": key, "User-Agent": USER_AGENT}, timeout=30
        )
    except httpx.HTTPError as exc:
        click.echo(f"{APP.status_prefix}error: Linear did not answer: {exc}", err=True)
        sys.exit(1)
    body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    viewer = ((body or {}).get("data") or {}).get("viewer") or {}
    if response.status_code != 200 or not viewer.get("id"):
        click.echo(f"{APP.status_prefix}error: Linear refused the API key (HTTP {response.status_code})", err=True)
        sys.exit(EXIT_USAGE)
    return key, str((viewer.get("organization") or {}).get("urlKey") or "linear")


def _run(target: Target, options: WatchOptions, config_path: Path | None, restart: str, header: list[str]) -> None:
    key, workspace = resolve(config_path)
    code = run_watch(
        APP,
        target,
        options,
        params={"api_key": key},
        writer=LinearWriter,
        resource_dir=resource_dir(workspace),
        readme=README,
        restart=restart,
        header=[f"workspace: {workspace}", *header],
    )
    sys.exit(code)


@click.group("watch")
def watch() -> None:
    """Follow Linear issues and report their changes as JSON events, one per line on stdout, or as messages into the
    Claude Code session that started the watch. Read-only.

    All watches on this machine share one daemon, which polls Linear's GraphQL API in one request per tick.
    """


@watch.command("issue")
@click.argument("issue")
@CONFIG_OPTION
@watch_options
def issue_command(issue: str, config_path: Path | None, options: WatchOptions) -> None:
    """Watch one issue (ABC-123 or its URL): state, assignee, labels, comments, attachments.

    The watch ends when the issue is completed, canceled or archived. To watch several issues, start one watch per
    issue; the shared daemon polls them in one request.
    """
    ident = issue_ref(issue)
    _run(Target("issue", ident), options, config_path, f"linear watch issue {ident}", [])


@watch.command("issues")
@click.option("--view", "view", help="A saved view: its slugId (the hex end of its URL), UUID or URL.")
@click.option("--team", "team", help="A team key, such as ENG.")
@click.option("--cycle", "cycle", help="With --team: 'active' (follows the rollover) or a cycle number.")
@CONFIG_OPTION
@watch_options
def issues_command(
    view: str | None, team: str | None, cycle: str | None, config_path: Path | None, options: WatchOptions
) -> None:
    """Watch the issues of a view, a team, or a team's cycle: changes, comments, issues entering and leaving.

    Runs until stopped.
    """
    if bool(view) == bool(team):
        raise click.UsageError("give exactly one of --view and --team")
    if cycle is not None and not team:
        raise click.UsageError("--cycle needs --team")
    if view:
        slug = view_ref(view)
        target = Target("view", slug)
        restart = f"linear watch issues --view {slug}"
    else:
        key = str(team).upper()
        if cycle is None:
            target = Target("team", key)
            restart = f"linear watch issues --team {key}"
        else:
            which = cycle.lower()
            if which != "active" and not which.isdigit():
                raise click.BadParameter("--cycle takes 'active' or a cycle number")
            target = Target("cycle", f"{key}/{which}")
            restart = f"linear watch issues --team {key} --cycle {which}"
    _run(target, options, config_path, restart, [])


watch.add_command(daemon_group(APP))
