"""The bin builds, its default config validates and the API key reaches the Authorization header. No network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from mcp_to_cli_kit.cli import build_cli
from mcp_to_cli_kit.client import distribution_version
from mcp_to_cli_kit.config import ConfigError, expand_server, load_config, save_config

from linear_mcp import DISTRIBUTION
from linear_mcp.cli import BIN, DEFAULT_CONFIG, LINEAR_MCP_URL

KEY = "lin_api_" + "x" * 32


@pytest.fixture(autouse=True)
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "CLAUDECODE", "LINEAR_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def config_file(home: Path, content: dict[str, object]) -> Path:
    return save_config(home / ".config" / "linear-mcp" / "config.yaml", content)


def invoke(*args: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    result = CliRunner().invoke(build_cli(BIN, DEFAULT_CONFIG, retry_delays=(0.0, 0.0)), list(args), env=env)
    return result.exit_code, result.stdout, result.stderr


def test_default_config_validates() -> None:
    loaded = load_config(BIN, default=DEFAULT_CONFIG, environ={})

    server = loaded.config.servers["linear"]
    assert server.url == LINEAR_MCP_URL
    assert server.mount == "root"
    assert server.headers == {"Authorization": "Bearer ${LINEAR_API_KEY}"}
    assert loaded.env_prefix == "LINEAR_MCP_"
    assert loaded.path == Path.home() / ".config" / "linear-mcp" / "config.yaml"


def test_the_key_comes_from_linear_api_key() -> None:
    server = load_config(BIN, default=DEFAULT_CONFIG, environ={}).config.servers["linear"]

    assert expand_server("linear", server, {"LINEAR_API_KEY": KEY}).headers == {"Authorization": f"Bearer {KEY}"}


def test_a_missing_key_names_the_variable_without_contacting_linear() -> None:
    server = load_config(BIN, default=DEFAULT_CONFIG, environ={}).config.servers["linear"]

    with pytest.raises(ConfigError, match="uses the environment variable LINEAR_API_KEY, which is not set"):
        expand_server("linear", server, {})


def test_the_config_file_header_replaces_the_template(home: Path) -> None:
    path = config_file(home, {"servers": {"linear": {"headers": {"Authorization": f"Bearer {KEY}"}}}})

    server = load_config(BIN, default=DEFAULT_CONFIG, config_path=path, environ={}).config.servers["linear"]

    assert expand_server("linear", server, {}).headers == {"Authorization": f"Bearer {KEY}"}


def test_old_config_shape_fails_clearly(home: Path) -> None:
    config_file(home, {"linear": {"api_key": KEY}})

    code, stdout, stderr = invoke("config")

    assert code == 2
    assert "linear: Extra inputs are not permitted" in stderr
    assert KEY not in stdout + stderr


def test_config_masks_the_key(home: Path) -> None:
    config_file(home, {"servers": {"linear": {"headers": {"Authorization": f"Bearer {KEY}"}}}})

    code, stdout, stderr = invoke("config", "--json", env={"LINEAR_API_KEY": KEY})

    assert code == 0
    assert KEY not in stdout + stderr
    headers = json.loads(stdout)["config"]["servers"]["linear"]["headers"]
    assert headers == {"Authorization": "Bearer ***" + KEY[-4:]}


def test_config_shows_the_template_unexpanded() -> None:
    code, stdout, _ = invoke("config", "--json", env={"LINEAR_API_KEY": KEY})

    assert code == 0
    assert KEY not in stdout
    assert json.loads(stdout)["config"]["servers"]["linear"]["headers"] == {"Authorization": "Bearer ${LINEAR_API_KEY}"}


def test_bin_builds_and_shows_its_version() -> None:
    result = CliRunner().invoke(build_cli(BIN, DEFAULT_CONFIG, distribution=DISTRIBUTION), ["--version"])

    assert result.exit_code == 0
    assert result.stdout.startswith(f"linear-mcp {distribution_version(DISTRIBUTION)} (mcp-to-cli-kit ")
