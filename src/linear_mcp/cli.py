"""CLI entry point for Linear MCP CLI."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import click
import httpx
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

from .client import LinearMcpClient, format_tool_result, get_tools
from .config import LINEAR_MCP_URL, get_config_path, load_config


def unwrap_exception(exc: BaseException) -> BaseException:
    """Unwrap ExceptionGroup/BaseExceptionGroup to get the root cause."""
    while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        exc = exc.exceptions[0]
    return exc


def format_error(exc: BaseException) -> str:
    """Format an exception into a user-friendly error message."""
    exc = unwrap_exception(exc)

    # Handle common HTTP/connection errors
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 401:
            return "Authentication failed. Check your LINEAR_API_KEY or run 'linear-mcp init'."
        if status == 403:
            return "Access denied. Your API key may lack required permissions."
        if status == 404:
            return "Resource not found. The MCP server endpoint may have changed."
        if status == 429:
            return "Rate limited. Please wait before making more requests."
        if status >= 500:
            return f"Linear server error ({status}). Try again later."
        return f"HTTP error {status}: {exc.response.text[:200] if exc.response.text else 'No details'}"

    if isinstance(exc, httpx.ConnectError):
        return "Connection failed. Check your internet connection or Linear server status."

    if isinstance(exc, httpx.TimeoutException):
        return "Request timed out. The server may be slow or unresponsive."

    if isinstance(exc, asyncio.TimeoutError):
        return "Operation timed out. Try increasing the timeout in your config."

    # Handle ExceptionGroup with multiple exceptions
    if isinstance(exc, BaseExceptionGroup):
        messages = [format_error(e) for e in exc.exceptions]
        return "; ".join(messages)

    # Default: use the exception message
    msg = str(exc)
    if not msg or msg == str(type(exc).__name__):
        return f"{type(exc).__name__}"
    return msg


console = Console()
error_console = Console(stderr=True)


def json_type_to_click_type(json_type: str | list | None) -> click.ParamType:
    """Convert JSON schema type to Click type."""
    if json_type is None:
        return click.STRING

    if isinstance(json_type, list):
        # Handle nullable types like ["string", "null"]
        non_null_types = [t for t in json_type if t != "null"]
        if non_null_types:
            json_type = non_null_types[0]
        else:
            return click.STRING

    type_map = {
        "string": click.STRING,
        "integer": click.INT,
        "number": click.FLOAT,
        "boolean": click.BOOL,
    }
    return type_map.get(json_type, click.STRING)


def parse_value(value: str, json_type: str | list | None) -> Any:
    """Parse a string value according to JSON schema type."""
    if value is None:
        return None

    # Handle arrays and objects - parse as JSON
    if isinstance(json_type, str) and json_type in ("array", "object"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    # Handle nullable types
    if isinstance(json_type, list):
        non_null_types = [t for t in json_type if t != "null"]
        if non_null_types:
            json_type = non_null_types[0]

    if json_type == "boolean":
        return value.lower() in ("true", "1", "yes")
    if json_type == "integer":
        return int(value)
    if json_type == "number":
        return float(value)

    return value


class DynamicGroup(click.Group):
    """A Click group that dynamically loads commands from MCP tools."""

    STATIC_COMMANDS = {"init", "config"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tools_cache: dict[str, Any] | None = None
        self._config = None

    def _load_config(self):
        """Load configuration."""
        if self._config is None:
            try:
                self._config = load_config()
            except Exception:
                self._config = None
        return self._config

    def _fetch_tools(self) -> dict[str, dict[str, Any]]:
        """Get tools as a dict keyed by name."""
        if self._tools_cache is not None:
            return self._tools_cache

        config = self._load_config()
        if config is None:
            return {}

        try:
            tools = get_tools(config)
        except BaseException as e:
            error_console.print(f"[red]Error fetching tools: {format_error(e)}[/red]")
            error_console.print("[dim]Using cached tools if available, or run with -v for details.[/dim]")
            return {}

        self._tools_cache = {t["name"]: t for t in tools}
        return self._tools_cache

    def list_commands(self, ctx: click.Context) -> list[str]:
        """List all available commands."""
        static_commands = list(self.STATIC_COMMANDS)
        try:
            tools = self._fetch_tools()
            tool_commands = list(tools.keys())
            return sorted(set(static_commands + tool_commands))
        except Exception:
            return static_commands

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Get a command by name."""
        # Check static commands first
        if cmd_name in self.commands:
            return self.commands[cmd_name]

        # Try to get dynamic command from MCP tools
        try:
            tools = self._fetch_tools()
            if cmd_name in tools:
                return self._create_tool_command(tools[cmd_name])
        except Exception:
            pass

        return None

    def _create_tool_command(self, tool: dict[str, Any]) -> click.Command:
        """Create a Click command from an MCP tool dict."""
        params = []
        schema = tool.get("inputSchema") or {}
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        # Map from Click's lowercased param name back to original MCP property name
        param_name_map = {}

        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get("type")
            prop_desc = prop_def.get("description", "")
            default = prop_def.get("default")
            is_required = prop_name in required

            # Handle array and object types as JSON strings
            click_type = click.STRING if prop_type in ("array", "object") else json_type_to_click_type(prop_type)

            # For array/object defaults, serialize to JSON string for CLI display
            cli_default = None
            if default is not None and prop_type in ("array", "object"):
                cli_default = json.dumps(default)
            elif default is not None:
                cli_default = default

            # Click lowercases parameter names, so we need to map back
            cli_param_name = prop_name.replace("_", "-")
            click_internal_name = cli_param_name.replace("-", "_").lower()
            param_name_map[click_internal_name] = prop_name

            # Create option
            option = click.Option(
                param_decls=[f"--{cli_param_name}"],
                type=click_type,
                required=is_required and default is None,
                default=cli_default,
                help=prop_desc[:200] if prop_desc else None,  # Truncate long descriptions
            )
            params.append(option)

        # Add output format option
        params.append(
            click.Option(
                param_decls=["--json", "as_json"],
                is_flag=True,
                default=False,
                help="Output raw JSON",
            )
        )

        def make_callback(tool_name: str, prop_defs: dict, name_map: dict):
            @click.pass_context
            def callback(ctx: click.Context, **kwargs):
                as_json = kwargs.pop("as_json", False)
                verbose = ctx.obj.get("verbose", False) if ctx.obj else False

                # Parse values according to their types
                arguments = {}
                for key, value in kwargs.items():
                    if value is not None:
                        # Map Click's lowercased param name back to original MCP property name
                        original_key = name_map.get(key, key)
                        prop_type = prop_defs.get(original_key, {}).get("type")
                        if prop_type in ("array", "object"):
                            arguments[original_key] = parse_value(str(value), prop_type)
                        else:
                            arguments[original_key] = value

                config = load_config()

                async def _call():
                    client = LinearMcpClient(config)
                    async with client.connect():
                        return await client.call_tool(tool_name, arguments)

                try:
                    with console.status(f"[bold green]Calling {tool_name}...[/bold green]"):
                        result = asyncio.run(_call())
                except BaseException as e:
                    error_console.print(f"[red]Error: {format_error(e)}[/red]")
                    if verbose:
                        error_console.print_exception()
                    sys.exit(1)

                if result.isError:
                    error_console.print("[red]Tool returned an error:[/red]")
                    error_console.print(format_tool_result(result), markup=False)
                    sys.exit(1)

                output = format_tool_result(result)

                if as_json:
                    print(output)  # Use plain print to avoid Rich's text wrapping
                else:
                    try:
                        data = json.loads(output)
                        console.print(JSON(json.dumps(data)))
                    except json.JSONDecodeError:
                        console.print(output, markup=False)

            return callback

        tool_name = tool["name"]
        return click.Command(
            name=tool_name,
            callback=make_callback(tool_name, properties, param_name_map),
            params=params,
            help=tool.get("description"),
        )


@click.group(cls=DynamicGroup)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=False, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable debug logging and show full tracebacks on error",
)
@click.pass_context
def cli(ctx: click.Context, config: Path | None, verbose: bool):
    """Linear MCP CLI - Query Linear using the MCP Server.

    Each Linear MCP tool is exposed as a CLI command.
    Use 'linear-mcp <command> --help' for details on each command.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose

    # Configure logging level based on verbose flag
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)


@cli.command("init")
@click.pass_context
def init_config(ctx: click.Context):
    """Initialize configuration file with credentials."""
    config_path = ctx.obj.get("config_path") or get_config_path()

    console.print("[bold]Linear MCP CLI Configuration[/bold]\n")

    # Prompt for credentials
    console.print("You can get your Linear API key from: https://linear.app/settings/api")
    api_key = click.prompt("Linear API Key", hide_input=True)

    # Create config file
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_content = f"""\
# Linear MCP CLI Configuration
# See https://linear.app/docs/mcp for more information

linear:
  api_key: "{api_key}"

mcp_server:
  timeout: 30
  sse_read_timeout: 300
"""

    with open(config_path, "w") as f:
        f.write(config_content)

    console.print(f"\n[green]Configuration saved to:[/green] {config_path}")


@cli.command("config")
@click.pass_context
def show_config(ctx: click.Context):
    """Show the current configuration (with secrets masked)."""
    config_path = ctx.obj.get("config_path")
    try:
        config = load_config(config_path)
    except Exception as e:
        error_console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)

    config_display = {
        "linear": {
            "api_key": "***" + config.linear.api_key[-4:] if config.linear.api_key else "(not set)",
        },
        "mcp_server": {
            "url": LINEAR_MCP_URL,
            "timeout": config.mcp_server.timeout,
            "sse_read_timeout": config.mcp_server.sse_read_timeout,
        },
    }

    console.print(Panel(JSON(json.dumps(config_display)), title="Current Configuration"))
    console.print(f"\n[dim]Config file: {get_config_path()}[/dim]")


def main():
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
