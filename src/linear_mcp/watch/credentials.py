"""The Linear API key for GraphQL, found the way `linear mcp` finds it.

The kit's config loading decides: the `Authorization` header of `~/.config/linear-mcp/config.yaml` (or `--config`)
wins, else the built-in `Bearer ${LINEAR_API_KEY}` template, expanded from the environment. GraphQL takes the personal
API key as `Authorization: <key>`; with a `Bearer ` prefix it answers 400, so the prefix is stripped.

The kit's config module loads pydantic, so it is imported only when a watch starts.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path


class MissingKey(Exception):
    """No usable key; the message says where one can go."""


def api_key(config_path: Path | None = None, environ: Mapping[str, str] | None = None) -> str:
    from mcp_to_cli_kit.config import ConfigError, expand_server, load_config

    from linear_mcp.cli import DEFAULT_CONFIG, MCP_BIN

    env = dict(os.environ if environ is None else environ)
    try:
        loaded = load_config(MCP_BIN, default=DEFAULT_CONFIG, config_path=config_path, environ=env)
        server = expand_server("linear", loaded.config.servers["linear"], env)
    except ConfigError as exc:
        raise MissingKey(str(exc)) from exc
    header = next((v for k, v in server.headers.items() if k.lower() == "authorization"), "")
    key = strip_bearer(header)
    if not key:
        raise MissingKey(f"no Linear API key: the Authorization header in {loaded.path} is empty")
    return key


def strip_bearer(value: str) -> str:
    return re.sub(r"^\s*Bearer\s+", "", value, flags=re.IGNORECASE).strip()
