"""`linear watch issue|issues|daemon`, on cli-watch-kit. Imported only when `linear watch` is used."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import click
from cli_watch_kit.cli import WatchOptions, daemon_group, run_watch, watch_options
from cli_watch_kit.source import Target

from linear_mcp.watch.app import APP
from linear_mcp.watch.credentials import MissingKey, api_key
from linear_mcp.watch.files import README, LinearWriter, resource_dir
from linear_mcp.watch.filters import FilterSpec

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


def check_filter(key: str, spec: FilterSpec, client: Any) -> list[str]:
    """The header lines of a filter; exits with a usage error when one of its teams or statuses does not exist.

    One request: the teams by key, with their states, and each status as Linear matches it in the filter (by name,
    case-insensitively, `triage` also by type) in the given teams or in all teams the key can read."""
    from linear_mcp.watch.filters import workflow_state_filter
    from linear_mcp.watch.graphql import API_URL, USER_AGENT
    from linear_mcp.watch.queries import STATES, TEAMS_STATES

    declarations: list[str] = []
    selections: list[str] = []
    variables: dict[str, Any] = {}
    if spec.teams:
        declarations.append("$t: [String!]!")
        selections.append(TEAMS_STATES)
        variables["t"] = list(spec.teams)
    for n, status in enumerate(spec.statuses):
        declarations.append(f"$s{n}: WorkflowStateFilter!")
        selections.append(STATES.format(alias=f"s{n}", var=f"s{n}"))
        variables[f"s{n}"] = workflow_state_filter(status, spec.teams)
    if not selections:
        return []
    document = f"query Check({', '.join(declarations)}) {{ {' '.join(selections)} }}"
    try:
        response = client.post(
            API_URL,
            json={"query": document, "variables": variables},
            headers={"Authorization": key, "User-Agent": USER_AGENT},
            timeout=30,
        )
        body = response.json()
    except Exception as exc:  # noqa: BLE001 - any failure here is "Linear did not answer"
        click.echo(f"{APP.status_prefix}error: Linear did not answer: {exc}", err=True)
        sys.exit(1)
    data = (body or {}).get("data") or {}
    if response.status_code != 200 or (body or {}).get("errors"):
        messages = "; ".join(str(e.get("message")) for e in (body or {}).get("errors") or [])
        click.echo(
            f"{APP.status_prefix}error: Linear refused the filter check: {messages or response.status_code}", err=True
        )
        sys.exit(1)

    def fail(message: str) -> None:
        click.echo(f"{APP.status_prefix}error: {message}", err=True)
        sys.exit(EXIT_USAGE)

    teams = {str(t.get("key")): t for t in (data.get("teams") or {}).get("nodes") or []}
    for key_ in spec.teams:
        if key_ not in teams:
            fail(f"no team {key_} (or no access to it)")
    header = []
    for n, status in enumerate(spec.statuses):
        matched = sorted({str((s.get("team") or {}).get("key")) for s in (data.get(f"s{n}") or {}).get("nodes") or []})
        if not matched and spec.teams:
            names = sorted(
                {str(s.get("name")) for t in teams.values() for s in (t.get("states") or {}).get("nodes") or []}
            )
            where = f"team {spec.teams[0]}" if len(spec.teams) == 1 else f"teams {', '.join(spec.teams)}"
            fail(f"no workflow state named {status!r} in {where}; its states: {', '.join(names)}")
        if not matched:
            fail(f"no workflow state named {status!r} in any team you can read")
        header.append(f"status: {status} ({len(matched)} team{'' if len(matched) == 1 else 's'})")
    return header


def _run(
    target: Target,
    options: WatchOptions,
    config_path: Path | None,
    restart: str,
    header: list[str],
    spec: FilterSpec | None = None,
) -> None:
    key, workspace = resolve(config_path)
    if spec is not None:
        import httpx

        with httpx.Client() as client:
            header = [*header, *check_filter(key, spec, client)]
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
@click.option(
    "--view", "view", help="A saved view: its slugId (the hex end of its URL), UUID or URL. Takes no other filter."
)
@click.option("--team", "teams", multiple=True, help="A team key, such as ENG. Repeatable: the issues of any of them.")
@click.option("--cycle", "cycle", help="With one --team: 'active' (follows the rollover) or a cycle number.")
@click.option(
    "--assignee",
    type=click.Choice(["me"], case_sensitive=False),
    help="me: the issues assigned to the API key's user; without --status, the open ones only.",
)
@click.option(
    "--status",
    "statuses",
    multiple=True,
    help="A workflow state name, case-insensitive, in each team's own workflow; repeatable: any of them. 'triage' "
    "also matches a renamed triage state. Without --team: in every team the key can read.",
)
@CONFIG_OPTION
@watch_options
def issues_command(
    view: str | None,
    teams: tuple[str, ...],
    cycle: str | None,
    assignee: str | None,
    statuses: tuple[str, ...],
    config_path: Path | None,
    options: WatchOptions,
) -> None:
    """Watch the issues of a view, teams, a team's cycle, assigned to me, or in some statuses: changes, comments,
    issues entering and leaving. The filters combine.

    Examples: --assignee me (newly assigned to me), --team ABC --status Triage (new in the triage of ABC).
    A filter with more than 2,000 issues ends at its first poll (watch_ended reason too_large). Runs until stopped.
    """
    if view and (teams or cycle is not None or assignee or statuses):
        raise click.UsageError("--view takes no other filter: a view has its own")
    if not (view or teams or assignee or statuses):
        raise click.UsageError("give --view, --team, --assignee me or --status")
    keys = sorted({t.strip().upper() for t in teams if t.strip()})
    if cycle is not None and len(keys) != 1:
        raise click.UsageError("--cycle needs exactly one --team")
    which = cycle.lower() if cycle is not None else None
    if which is not None and which != "active" and not which.isdigit():
        raise click.BadParameter("--cycle takes 'active' or a cycle number")
    if view:
        slug = view_ref(view)
        _run(Target("view", slug), options, config_path, f"linear watch issues --view {slug}", [])
    elif len(keys) == 1 and not assignee and not statuses:
        key = keys[0]
        if which is None:
            _run(Target("team", key), options, config_path, f"linear watch issues --team {key}", [])
        else:
            restart = f"linear watch issues --team {key} --cycle {which}"
            _run(Target("cycle", f"{key}/{which}"), options, config_path, restart, [])
    else:
        if any(not s.strip() for s in statuses):
            raise click.BadParameter("--status takes a state name")
        spec = FilterSpec.of(tuple(keys), which, assignee is not None, statuses)
        _run(spec.target(), options, config_path, spec.restart(), [], spec)


watch.add_command(daemon_group(APP))
