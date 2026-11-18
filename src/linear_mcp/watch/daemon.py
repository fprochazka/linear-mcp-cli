"""What `python -m linear_mcp.watch.daemon` runs: the shared daemon of `linear watch`. Watchers start it."""

from cli_watch_kit.daemon import main

from linear_mcp.watch.app import APP

if __name__ == "__main__":
    main(APP)
