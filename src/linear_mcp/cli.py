"""``linear``: Linear from the command line, with the tools of Linear's official MCP server under ``linear mcp``.

``linear-mcp`` is the same as ``linear mcp``. Only click is imported at start-up: the MCP SDK, httpx and
pydantic load when the ``mcp`` group is used, so ``linear --help`` and the commands outside it stay fast.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import click
from mcp_to_cli_kit.lazy import mount, run

from linear_mcp import DISTRIBUTION

BIN = "linear"

# Names the kit's config and cache directories (~/.config/linear-mcp, ~/.cache/linear-mcp) and its env prefix.
MCP_BIN = "linear-mcp"

LINEAR_MCP_URL = "https://mcp.linear.app/mcp"

DEFAULT_CONFIG: dict[str, Any] = {
    "help": (
        "Linear MCP CLI - Query and update Linear through its MCP server. Each tool is a command; use "
        "'linear mcp <command> --help' for its options. Needs a Linear API key in LINEAR_API_KEY or in "
        "~/.config/linear-mcp/config.yaml."
    ),
    "servers": {
        "linear": {
            "url": LINEAR_MCP_URL,
            # Expanded when the server is contacted; a key in the config file replaces the whole header.
            "headers": {"Authorization": "Bearer ${LINEAR_API_KEY}"},
        }
    },
}


def mcp_group() -> click.Group:
    """The kit CLI with one command per tool of Linear's MCP server, as ``linear mcp`` and ``linear-mcp``."""
    from mcp_to_cli_kit.cli import build_cli

    return build_cli(MCP_BIN, DEFAULT_CONFIG, distribution=DISTRIBUTION)


def watch_group() -> click.Group:
    """`linear watch`, which follows issues through Linear's GraphQL API."""
    from linear_mcp.watch.cli import watch

    return watch


def linear_group() -> click.Group:
    @click.group(name=BIN)
    @click.version_option(package_name=DISTRIBUTION, prog_name=BIN, message="%(prog)s %(version)s")
    def linear() -> None:
        """Linear from the command line."""

    mount(linear, "mcp", help="Call the tools of Linear's MCP server.", factory=mcp_group)
    mount(
        linear, "watch", help="Follow issues, views, teams and cycles, and report their changes.", factory=watch_group
    )
    return linear


def main(args: Sequence[str] | None = None) -> None:
    run(linear_group(), prog_name=BIN, args=args)


def mcp_main(args: Sequence[str] | None = None) -> None:
    """``linear-mcp``, the same command as ``linear mcp``."""
    run(mcp_group(), prog_name=MCP_BIN, args=args)
