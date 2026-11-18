"""The resource dir of one watch: `state.json` from each snapshot, and one Markdown file per reported comment.

Layout: `<base>/<workspace>/issues/<ID>`, `.../teams/<KEY>`, `.../teams/<KEY>/cycles/<N|active>`, `.../views/<slugId>`.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any

from cli_watch_kit.atomic import atomic_write_json, atomic_write_text
from cli_watch_kit.client import WriterContext
from cli_watch_kit.events import Event
from cli_watch_kit.paths import sanitize_part
from cli_watch_kit.source import Target

README = """Files of one `linear watch`:

- events.jsonl: every reported event, one JSON object per line.
- baseline.json: the snapshot the watch resumes from.
- state.json: the newest snapshot (issues, comment times).
- comments/: one Markdown file per reported comment, named <created>-<author>-<comment id>.md.
"""


def resource_dir(workspace: str) -> Any:
    def place(base: Path, target: Target) -> Path:
        root = base / sanitize_part(workspace)
        if target.kind == "issue":
            return root / "issues" / sanitize_part(target.id)
        if target.kind == "team":
            return root / "teams" / sanitize_part(target.id)
        if target.kind == "cycle":
            key, cycle = target.id.split("/", 1)
            return root / "teams" / sanitize_part(key) / "cycles" / sanitize_part(cycle)
        return root / "views" / sanitize_part(target.id)

    return place


class LinearWriter:
    def __init__(self, context: WriterContext) -> None:
        self.dir = context.resource_dir

    def snapshot(self, data: Any) -> None:
        if data is not None:
            atomic_write_json(self.dir / "state.json", data)

    def attach(self, events: list[Event]) -> list[Event]:
        out = []
        for event in events:
            body = event.data.get("body")
            if event.kind.startswith("comment_") and isinstance(body, str):
                path = self._comment_file(event, body)
                data = {k: v for k, v in event.data.items() if k != "body"}
                event = dataclasses.replace(event, data=data, artifacts=(*event.artifacts, str(path)))
            out.append(event)
        return out

    def _comment_file(self, event: Event, body: str) -> Path:
        data = event.data
        created = re.sub(r"[^0-9T]", "", str(data.get("created_at") or ""))[:15] or "unknown"
        author = sanitize_part(str(data.get("author") or "unknown"))
        path = self.dir / "comments" / f"{created}-{author}-{sanitize_part(str(data.get('comment_id')))}.md"
        header = (
            f"<!-- {data.get('issue')} comment {data.get('comment_id')} by {data.get('author')}, "
            f"created {data.get('created_at')}, {event.kind} -->\n\n"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, header + body + ("\n" if not body.endswith("\n") else ""))
        return path
