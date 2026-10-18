"""``linear-mcp``: the tools of Linear's official MCP server (issues, projects, teams, documents, ...)."""

from __future__ import annotations

from typing import Any

from mcp_to_cli_kit.cli import main as kit_main

from linear_mcp import DISTRIBUTION

BIN = "linear-mcp"

LINEAR_MCP_URL = "https://mcp.linear.app/mcp"

DEFAULT_CONFIG: dict[str, Any] = {
    "help": (
        "Linear MCP CLI - Query and update Linear through its MCP server. Each tool is a command; use "
        "'linear-mcp <command> --help' for its options. Needs a Linear API key in LINEAR_API_KEY or in "
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


def main() -> None:
    kit_main(BIN, DEFAULT_CONFIG, distribution=DISTRIBUTION)
