---
name: linear-watch
description: >-
  This skill should be used when the session has to wait for something on Linear or react to it as it happens:
  "watch this issue", "tell me when the ticket moves", "let me know when someone comments on ABC-123", "watch the
  cycle", "watch my view", "follow the team's issues", or when a `<linear-watcher>` message arrives. Covers starting
  `linear watch` in the background, its startup header, event filters, reacting to its messages, stopping it, and
  the files it writes.
trigger-keywords: linear watch, linear-watcher, watch issue, watch ticket, watch cycle, watch view
allowed-tools: Bash(linear watch issue:*), Bash(linear watch issues:*), Bash(linear watch daemon status:*), Bash(linear watch daemon logs:*), Bash(linear watch --help), Bash(linear watch daemon --help), Bash(linear watch daemon stop --help)
---

# linear watch

`linear watch` follows Linear issues and reports each change as an event. Under Claude Code the events arrive in this conversation as messages, so the session learns about a state change or a new comment without asking. It only reads Linear; it never changes anything. It comes with the `linear` command of linear-mcp-cli.

## Watch or read once

- "What is it now?": read once with `linear mcp get-issue --id ABC-123` or `linear mcp list-comments --issue-id ABC-123` (the `linear-mcp-cli` skill).
- "Tell me when it changes": start a watcher. **Never poll** with `sleep`, a loop or repeated reads. All watchers on the machine share one daemon that asks Linear once per tick for all of them.

## Starting a watcher

Start every watcher with the Bash tool and `run_in_background: true`, one watcher per resource:

```bash
linear watch issue ABC-123                       # one issue, by identifier or URL; one watch per issue
linear watch issues --team ABC                   # every issue of a team
linear watch issues --team ABC --cycle active    # the team's active cycle; follows the rollover
linear watch issues --team ABC --cycle 42        # one cycle by number
linear watch issues --view 0123456789ab          # a saved view: its slugId, the hex end of its URL, or the URL
```

- An issue watch ends when the issue is completed, canceled or archived (`watch_ended` with that reason). An issue that is already closed when the watch starts keeps being watched. An issues watch runs until stopped.
- To follow several issues, start one watcher per issue. The daemon polls them in one request, so this costs nothing extra.
- `--until=<kind>` ends after the first event of that kind (`--until=state_changed`), `--timeout=<duration>` after that long, `--idle-after=<duration>` when nothing was reported for that long.
- The API key is found as `linear mcp` finds it: the `Authorization` header in `~/.config/linear-mcp/config.yaml` (or `--config PATH`), else `LINEAR_API_KEY`. A missing or refused key exits 2 before anything starts.
- **Start watchers from the main session.** Claude Code has no route for messages to a subagent, so a subagent's watcher would message the main session anyway. Forward the events a subagent needs with SendMessage: the event lines and the comment file paths, not a summary.

### Leave `--events-stream` at its default

Start every watcher without `--events-stream`. The default, `auto`, sends each event to this session as a message when the session accepts them, and otherwise falls back to stdout and says why. With `--events-stream=stdout` nothing tells you when an event arrives; that mode is for scripts and terminals.

## The startup header

Read the header in the background task's output first. Each line starts with `linear watch: `:

- `stream:` confirms the mode. A `stream fallback:` line means the events do not arrive as messages: tell the user the reason; the events are in the task output and in `events.jsonl`.
- `dir:` and `changelog:` name the resource dir and its `events.jsonl`. Take paths from here and from the events, never build them.
- `workspace:` is the Linear workspace of the key.
- `events:` and `ignored:` show the filter, `ends:` the end options, `daemon:` the shared daemon or `--no-daemon`.
- `restart with:` is the command to start again with another filter.

## Filters

`--events=<kinds or groups>` reports only those, `--exclude-events=<kinds or groups>` leaves them out. Groups: `status`, `comments`, `links`, `scope`; `lifecycle` (`watch_started`, `watch_degraded`, `watch_ended`) is always on. An unknown kind, or one the resource never produces, is a start-up error.

- Waiting for a ticket to move: `linear watch issue ABC-123 --events=status --until=state_changed`.
- Following a discussion: `--events=comments`.
- A cycle or view as a queue: `--events=scope` reports only issues entering and leaving.

## The messages

Each batch arrives as one message, one JSON event per line:

```text
<linear-watcher resource="issue ABC-123" seq="4-5">
{"kind":"state_changed","seq":4,"data":{"issue":"ABC-123","title":"…","url":"…","from":"Todo","to":"In Progress","to_type":"started","actor":"Jane Doe","actor_is_me":false}}
{"kind":"comment_created","seq":5,"data":{"issue":"ABC-123","comment_id":"…","author":"Jane Doe","actor_is_me":false,"excerpt":"Could you …"},"artifacts":["/…/issues/ABC-123/comments/20260110T100030-Jane-Doe-….md"]}
</linear-watcher>
```

- `artifacts` paths are absolute. A comment event carries a 300-character `excerpt`; the whole comment is in the file.
- `actor_is_me` is true for changes made with the same Linear account as the watcher, which includes your own changes through `linear mcp`. Do not react to your own changes as if someone else made them.
- A batch above 64 KB arrives as counts per kind, and a gap in `seq` means messages were lost: read `events.jsonl` from the last `seq` you saw.

## The events

| Kind | Resource | Data besides `issue`, `title`, `url` |
|------|----------|---------------------------------------|
| `state_changed` | all | `from`, `to`, `to_type` (`backlog`, `unstarted`, `started`, `completed`, `canceled`, `triage`), `actor`, `actor_is_me` |
| `assignee_changed`, `delegate_changed` | all | `from`, `to` (names), `actor`, `actor_is_me` |
| `priority_changed`, `title_changed`, `project_changed`, `cycle_changed` | all | `from`, `to` |
| `labels_changed` | all | `added`, `removed` |
| `comment_created`, `comment_edited`, `comment_resolved`, `comment_unresolved` | all | `comment_id`, `parent_id`, `author`, `excerpt`; the comment file in `artifacts` |
| `comment_deleted` | issue | `comment_id` |
| `attachment_added` | all | `attachment_title`, `attachment_url`, `source` (`gitlab`, `github`, …): how merge requests and pull requests show up |
| `issue_entered`, `issue_left` | team, cycle, view | `state`; `issue_left` also `reason` (`moved`, `archived`, `relisted`) |
| `active_cycle_changed` | cycle with `--cycle active` | `team`, `from`, `to` (cycle numbers) |

Reactions to comments are not reported.

## Reacting

- **`state_changed`**: compare `to_type` with what the caller waits for; `completed` and `canceled` end an issue watch.
- **`comment_created`, `comment_edited`**: read only the comment file in `artifacts`, and note who wrote it.
- **`attachment_added`** with a merge request or pull request: the work on the issue has a review to follow.
- **`issue_entered`, `issue_left`**: a queue changed; act as the caller's purpose says.
- **`watch_degraded`**: `auth`, tell the user the key was refused; `rate_limited`, nothing to do, the daemon waits; `not_found`, check the ID; `error`, nothing to do unless it repeats.
- **`watch_ended`**: the reason says why: `completed`, `canceled`, `archived`, `not_found`, `until`, `timeout`, `idle`, `session_gone`, or a signal.

## Stopping

Stop a watcher by stopping its background task. To change a filter, stop it and start the `restart with:` command. Never leave two watchers on the same resource with the same filter.

## The files

Each resource has one dir under the session scratchpad, `linear-watch/<workspace>/issues/<ID>`, `…/teams/<KEY>`, `…/teams/<KEY>/cycles/<N|active>` or `…/views/<slugId>`, with a `README.txt`:

- `events.jsonl`: every event; `state.json`: the newest snapshot; `baseline.json`: what the watcher resumes from.
- `comments/`: one Markdown file per reported comment.

`linear watch daemon status` shows the daemon's subscriptions, how many requests served how many targets, and the API budget; `linear watch daemon logs` its log; `linear watch daemon stop` stops it (running watchers start a new one); it asks for permission, because it interrupts every watch on the machine.

## Limits

- Changes are seen within the poll interval (30 s for an issue, 60 s for an issues watch) plus up to 5 s.
- A deleted comment is reported only by an issue watch. A view's membership is checked against Linear's own view list every 10 minutes and whenever the view changes, so an issue that leaves a view without being changed itself (a relative date filter) is reported up to 10 minutes late.
- An issues watch on a team starts from its open issues; an old closed issue that gets a change is followed from then on without an `issue_entered`.
