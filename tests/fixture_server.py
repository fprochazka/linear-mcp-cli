"""A stand-in for Linear's MCP server, run with uvicorn on a localhost port, with a recorder of the tool calls."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass, field
from typing import Annotated, Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]

MISSING_ISSUE = "ABC-404"


@dataclass
class Recorder:
    """Keeps the JSON-RPC method of every request in front of an ASGI app."""

    app: AsgiApp
    methods: list[str] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def reset(self) -> None:
        self.methods.clear()
        self.calls.clear()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        payload = json.loads(body) if body else None
        if isinstance(payload, dict) and isinstance(payload.get("method"), str):
            self.methods.append(payload["method"])
            if payload["method"] == "tools/call":
                self.calls.append(payload.get("params") or {})

        sent = False

        async def replay() -> Message:
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


def build_server() -> FastMCP:
    mcp = FastMCP("linear", stateless_http=True, json_response=True)

    @mcp.tool(structured_output=False)
    def get_issue(
        id: Annotated[str, Field(description="Issue ID or identifier (e.g., LIN-123)")],
        includeRelations: Annotated[bool, Field(description="Include blocking/related/duplicate relations")] = False,
    ) -> str:
        """Retrieve detailed information about an issue by ID."""
        if id == MISSING_ISSUE:
            raise ToolError(f"Entity not found: Issue - Could not find referenced Issue {id}.")
        return json.dumps({"identifier": id, "title": "Fix the login", "relations": includeRelations})

    @mcp.tool(structured_output=False)
    def list_teams(query: str | None = None) -> str:
        """List teams in the user's Linear workspace."""
        return json.dumps({"teams": [{"key": "ABC", "name": "Engineering"}]})

    return mcp


@dataclass
class RunningServer:
    url: str
    recorder: Recorder
    server: uvicorn.Server
    thread: threading.Thread

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)


def start() -> RunningServer:
    """Start the server on a free port."""
    recorder = Recorder(build_server().streamable_http_app())
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(recorder, log_level="error", lifespan="on", ws="none", timeout_graceful_shutdown=1)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("the fixture server did not start")
        time.sleep(0.01)
    return RunningServer(f"http://127.0.0.1:{port}/mcp", recorder, server, thread)
