"""MCP Client for connecting to the Linear MCP Server."""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent, Tool

from .cache import load_from_cache, save_to_cache
from .config import LINEAR_MCP_URL, Config


class LinearMcpClient:
    """Client for interacting with the Linear MCP Server."""

    def __init__(self, config: Config):
        self.config = config
        self._session: ClientSession | None = None

    def _get_headers(self) -> dict[str, str]:
        """Get authentication headers for the MCP server."""
        return {
            "Authorization": f"Bearer {self.config.linear.api_key}",
        }

    @asynccontextmanager
    async def connect(self):
        """Connect to the MCP server and yield a session."""
        headers = self._get_headers()

        async with (
            streamablehttp_client(
                url=LINEAR_MCP_URL,
                headers=headers,
                timeout=self.config.mcp_server.timeout,
                sse_read_timeout=self.config.mcp_server.sse_read_timeout,
            ) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            self._session = session
            try:
                yield session
            finally:
                self._session = None

    async def list_tools(self) -> list[Tool]:
        """List all available tools from the MCP server."""
        if self._session is None:
            raise RuntimeError("Not connected to MCP server. Use 'async with client.connect()' first.")

        result = await self._session.list_tools()
        return list(result.tools)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        """Call a tool on the MCP server."""
        if self._session is None:
            raise RuntimeError("Not connected to MCP server. Use 'async with client.connect()' first.")

        return await self._session.call_tool(tool_name, arguments=arguments or {})


def format_tool_result(result: CallToolResult) -> str:
    """Format a tool result for display."""
    output_parts = []

    for content in result.content:
        if isinstance(content, TextContent):
            # Try to parse as JSON for pretty printing
            try:
                data = json.loads(content.text)
                output_parts.append(json.dumps(data, indent=2))
            except json.JSONDecodeError:
                output_parts.append(content.text)
        else:
            output_parts.append(str(content))

    return "\n".join(output_parts)


def get_tools(config: Config) -> list[dict[str, Any]]:
    """Get MCP tools, using cache if available.

    Args:
        config: The application configuration.

    Returns:
        List of tool dictionaries with name, description, and inputSchema.
    """
    if not config.linear.api_key:
        return []

    # Try cache first
    cached = load_from_cache()
    if cached is not None:
        return cached

    # Fetch from MCP server
    async def _fetch():
        client = LinearMcpClient(config)
        async with client.connect():
            return await client.list_tools()

    try:
        tools = asyncio.run(_fetch())
        tools_data = [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema,
            }
            for t in tools
        ]
        save_to_cache(tools_data)
        return tools_data
    except Exception:
        return []
