"""The `WatchApp` of `linear watch`. Importing this module builds no source and imports no HTTP client."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from cli_watch_kit.app import WatchApp
from cli_watch_kit.source import Source

from linear_mcp import DISTRIBUTION


def make_source() -> Source[object]:
    from linear_mcp.watch.source import LinearSource

    return LinearSource()  # type: ignore[return-value]


def _version() -> str:
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return "0"


APP = WatchApp(
    name="linear-watch",
    source=make_source,
    daemon_module="linear_mcp.watch.daemon",
    app_protocol=1,
    version=_version(),
    status_prefix="linear watch: ",
    envelope_tag="linear-watcher",
    command="linear watch",
)
