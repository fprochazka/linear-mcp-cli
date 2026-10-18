---
name: linear-mcp-cli
description: CLI for querying and updating Linear (issues, projects, teams, documents, comments). Use when managing issues, creating/updating tasks, exploring projects, or integrating Linear with workflows. Triggered by requests involving Linear data, issue tracking, or project management.
trigger-keywords: linear, issue, issues, tasks, task, ticket, tickets
allowed-tools: Bash(linear-mcp --help), Bash(linear-mcp --refresh-tools --help), Bash(linear-mcp config:*), Bash(linear-mcp schema:*), Bash(linear-mcp get-agent-skill:*), Bash(linear-mcp get-attachment:*), Bash(linear-mcp get-document:*), Bash(linear-mcp get-initiative:*), Bash(linear-mcp get-issue:*), Bash(linear-mcp get-issue-status:*), Bash(linear-mcp get-milestone:*), Bash(linear-mcp get-notifications:*), Bash(linear-mcp get-project:*), Bash(linear-mcp get-release:*), Bash(linear-mcp get-release-note:*), Bash(linear-mcp get-status-updates:*), Bash(linear-mcp get-team:*), Bash(linear-mcp get-template:*), Bash(linear-mcp get-triage-responsibility:*), Bash(linear-mcp get-user:*), Bash(linear-mcp get-workspace:*), Bash(linear-mcp list-agent-skills:*), Bash(linear-mcp list-comments:*), Bash(linear-mcp list-custom-views:*), Bash(linear-mcp list-customer-needs:*), Bash(linear-mcp list-customers:*), Bash(linear-mcp list-cycles:*), Bash(linear-mcp list-documents:*), Bash(linear-mcp list-initiative-labels:*), Bash(linear-mcp list-initiatives:*), Bash(linear-mcp list-issue-labels:*), Bash(linear-mcp list-issue-statuses:*), Bash(linear-mcp list-issues:*), Bash(linear-mcp list-milestones:*), Bash(linear-mcp list-project-labels:*), Bash(linear-mcp list-projects:*), Bash(linear-mcp list-release-notes:*), Bash(linear-mcp list-release-pipelines:*), Bash(linear-mcp list-releases:*), Bash(linear-mcp list-teams:*), Bash(linear-mcp list-templates:*), Bash(linear-mcp list-users:*), Bash(linear-mcp search-documentation:*), Bash(linear-mcp save-issue --help), Bash(linear-mcp save-comment --help), Bash(linear-mcp save-document --help), Bash(linear-mcp save-project --help), Bash(linear-mcp save-issue-label --help)
---

# Linear MCP CLI

CLI tool providing direct access to Linear data through Linear's official MCP server. Each tool is a command; `linear-mcp --help` lists them all, including the ones not covered here (initiatives, milestones, cycles, releases, customers, attachments, notifications, ...).

## ⚠️ Mutating commands are NOT idempotent — never re-run a create to inspect its output

`save-issue` (without `--id`), `save-project`, `save-comment` (without `--id`), `save-document` (without `--id`/slug), and `save-issue-label` (without `--id`) **create a brand-new record on every invocation**. Running one twice makes a duplicate.

**The exact trap that has caused duplicate tickets more than once:** you run a create, pipe it through `grep`/`jq`/`tail`/`head` to pull the identifier or URL, the filter matches nothing (a field you expected is named differently, or the shape differs), you read the empty output as *"it didn't return what I wanted / it didn't work"* and re-run the same command — but the **first create already succeeded**. Now there are two tickets.

**Hard rules — follow all of them:**

1. **Run a create with NO output filter.** Never pipe a `save-*` create through `grep`/`jq`/`tail`/`head`. Print the whole response and read the `id`/`identifier`/`url` straight from it — the response always contains them. Filtering is what hides success and triggers the fatal retry.
2. **Never re-run a create to reformat, re-extract, or "just get the URL" of something you just made.** If you missed a field, DO NOT re-create — look it up with a **read-only** `get-issue`/`list-issues` instead.
3. **If a create's result looks empty, errored inside a pipe, or is ambiguous, assume it MAY have succeeded.** Verify with `list-issues`/`get-issue` **before** retrying. Only retry a create after you've confirmed nothing was created.
4. **After a create, every further change uses `--id`** (that UPDATES and is safe to repeat). A `save-*` *with* `--id` = update; *without* `--id` = create. When in doubt, check for the `--id`.

## Quick Reference

| Entity | Commands | Reference |
|--------|----------|-----------|
| **Issues** | `list-issues`, `get-issue`, `save-issue` | *(below)* |
| **Projects** | `list-projects`, `get-project`, `save-project`, `list-project-labels` | [projects.md](references/projects.md) |
| **Teams** | `list-teams`, `get-team`, `list-issue-statuses`, `get-issue-status`, `list-cycles` | [teams.md](references/teams.md) |
| **Users** | `list-users`, `get-user` | [users.md](references/users.md) |
| **Labels** | `list-issue-labels`, `save-issue-label` | [labels.md](references/labels.md) |
| **Documents** | `list-documents`, `get-document`, `save-document` | [documents.md](references/documents.md) |
| **Comments** | `list-comments`, `save-comment` | [comments.md](references/comments.md) |
| **Docs** | `search-documentation` | [docs.md](references/docs.md) |

## Parameter Resolution

Most parameters accept human-readable names. The MCP server resolves them to internal IDs.

| Parameter | Accepts | Example |
|-----------|---------|---------|
| `--team`, `--project`, `--state`, `--cycle`, `--milestone`, `--label`, `--initiative` | Name (case-insensitive) or ID; teams also take their key, states their type. Projects need the **exact full name** | `--team "Engineering"` |
| `--assignee`, `--member`, `--lead` | User ID, name, email, or `"me"` | `--assignee "me"` |
| `--labels` (array) | Names or IDs | `'["bug", "critical"]'` |

Teams accept their full name, their key (the issue prefix) or ID. States accept a status name, a status type (`started`, `backlog`, ...) or ID. **Projects need the exact full name** (or ID); a partial name is not found.

| Filter | Works | Doesn't work |
|--------|-------|--------------|
| `--team` | `"Frontend Engineering"` (name), `"FE"` (key), or ID | |
| `--project` | `"API Redesign (Q1 2025)"` (full name) or ID | `"API Redesign"` (partial) |
| `--state` | `"In Progress"` (name), `"started"` (type), or ID | |

To find correct names, first run `list-teams`, `list-projects`, or `list-issue-statuses --team "Team Name"`.

**Issue ID or identifier** (e.g., `ABC-123`) — accepted in:

| Parameter | Context |
|-----------|---------|
| `--id` | `get-issue`, `save-issue` |
| `--issue-id` | `list-comments`, `save-comment` |
| `--parent-id` | `save-issue` (sub-issues) |
| `--blocks`, `--blocked-by`, `--related-to`, `--duplicate-of` | `save-issue` relations (e.g., `'["ABC-123"]'`) |
| `--remove-blocks`, `--remove-blocked-by`, `--remove-related-to` | `save-issue` relation removal |

**Internal UUID required** (from prior `list-*` or `get-*` calls):

| Parameter | Context |
|-----------|---------|
| `--id` | `save-project`, `save-comment` (update) |
| `--id` (or slug) | `get-document`, `save-document` (update) |
| `--team-id` | `list-cycles`, `save-issue-label` |
| `--parent-id` | `save-comment` (replies) |
| `--project-id`, `--initiative-id`, `--creator-id` | `list-documents` filters |

## Arrays, objects and null

Arrays take the option once per item, or one JSON array literal:

```bash
--labels bug --labels critical
--labels '["bug", "critical"]'
--links '[{"url": "https://github.com/...", "title": "PR"}]'
```

Objects take a JSON literal; invalid JSON is a usage error. Values are never split on commas.

Where a tool's help says "Null to remove" (`--duplicate-of`, `--parent-id`, `--assignee`, `--lead`, ...), send the null through `--input-json`, which merges with the other options:

```bash
linear-mcp save-issue --id "ABC-123" --input-json '{"duplicateOf": null}'
```

## Priority Values

| Value | Issue | Project |
|-------|-------|---------|
| `0` | No priority | No priority |
| `1` | Urgent | Urgent |
| `2` | High | High |
| `3` | Medium | Medium |
| `4` | Low | Low |

## Content Preparation Workflow (REQUIRED for long content)

**For any argument longer than a few words (descriptions, comments, document bodies), you MUST write it to a file and pass it with `--arg-file NAME=PATH`** rather than inlining it. This prevents shell escaping issues, preserves formatting, lets the user review before submission, and keeps edits cheap. `--arg-file NAME=-` reads the value from stdin.

- If the content already exists as a file on disk, use it directly — do **not** copy it into the scratchpad first.
- When generating new content, write it to a file in the session **scratchpad directory** (from your system prompt), named uniquely for the ticket/document (e.g., `<scratchpad>/desc-ENG-123.md`, `<scratchpad>/comment-ENG-456.md`). **Never** use generic names like `desc.md` — they collide across tickets.
- Reuse the same file for the same ticket/document across edits — the Write tool diff shows the user exactly what changed.

| Parameter | Example |
|-----------|---------|
| `--description` | `--arg-file description=<scratchpad>/desc-ENG-123.md` |
| `--body` | `--arg-file body=<scratchpad>/comment-ENG-123.md` |
| `--content` | `--arg-file content=<scratchpad>/doc-roadmap-q2.md` |

`NAME` is the option or the property name. **Short, single-line values** (titles, names, summaries) can be passed directly as strings.

## Options and output

- Commands and options are kebab case (`get-issue --include-relations`, `list-documents --project-id`). The tools' own names (`get_issue`) and the schema's camelCase options (`--includeRelations`, `--projectId`) still work.
- An option left out is not sent; the server applies its default.
- Booleans are `--x` / `--no-x` (`--include-archived` / `--no-include-archived`). There is no `--x true` form.
- `--input-json '{...}'` (or `@file`, or `-` for stdin) passes all arguments as one JSON object, merged with the options given.
- `linear-mcp schema <command>` prints a tool's raw input schema; `linear-mcp <command> --help` its full description and options.
- Under an AI agent, or with `--json`, the result is printed exactly as the server sent it; `--pretty` indents JSON. Pipe either into `jq` — but never a create (see above).
- Exit codes: 0 success; 1 the tool reported an error (message on stderr); 2 a usage or config error (the tool's parameter list is printed); 3 Linear could not be reached; 130 interrupted.
- A call times out after 100 s; raise it with `LINEAR_MCP_SERVERS__LINEAR__SSE_READ_TIMEOUT=300`.
- The API key comes from `LINEAR_API_KEY`, or from the `Authorization` header in `~/.config/linear-mcp/config.yaml`. A missing key exits 2 and names the variable. `linear-mcp config` shows the effective configuration with the key masked.
- The tool list is cached for an hour; `linear-mcp --refresh-tools --help` fetches it again.

---

# Issues Reference

## list-issues

List issues in the workspace with filters.

```bash
# My issues
linear-mcp list-issues --assignee "me"

# Filter by state and team
linear-mcp list-issues --state "In Progress" --team "Engineering"

# By project
linear-mcp list-issues --project "Q1 Roadmap"

# Recently updated
linear-mcp list-issues --updated-at "-P1D"

# Combine filters
linear-mcp list-issues --team "Engineering" --state "In Progress" --assignee "me" --limit 25
```

| Option | Description |
|--------|-------------|
| `--assignee` | User ID, name, email, or `"me"` |
| `--delegate` | Agent name or ID |
| `--team` | Team name, key (the issue prefix), or ID |
| `--state` | Status name (`"In Progress"`), status type (`"started"`), or ID |
| `--project` | **Exact** project name or ID (partial names don't work) |
| `--cycle` | Cycle name or ID |
| `--label` | Label name or ID |
| `--query` | Search in title/description |
| `--parent-id` | Parent issue UUID (for sub-issues) |
| `--created-at`, `--updated-at` | ISO-8601 or duration (e.g., `-P1D`) |
| `--limit` | Max results (default 50, max 250) |
| `--include-archived` | Include archived issues (default false) |

## get-issue

Get detailed issue info including attachments and git branch name.

```bash
linear-mcp get-issue --id "ABC-123"

# Include relations (blocking, related, duplicate)
linear-mcp get-issue --id "ABC-123" --include-relations
```

**Note:** `--id` accepts either the internal UUID or the issue identifier (e.g., `ABC-123`).

## save-issue

Create or update an issue. If `--id` is provided, updates the existing issue; otherwise creates a new one. When creating, `--title` and `--team` are required.

> **Creating (no `--id`) is a non-idempotent mutation — see the ⚠️ section at the top.** Run the create unpiped, read the `identifier`/`url` from the full response, and never re-run it to fetch a field you missed (use `get-issue`/`list-issues` for that). A second run = a duplicate ticket.

```bash
# Create basic (no description)
linear-mcp save-issue --team "Engineering" --title "Fix login bug"

# Create with description (write to file first, see "Content Preparation Workflow" above)
linear-mcp save-issue --team "Engineering" --title "Fix login bug" \
  --arg-file description=<scratchpad>/issue-desc-UNIQUE.md \
  --assignee "me" \
  --priority 2 \
  --state "To Do" \
  --labels '["bug", "auth"]'

# Create with project and due date
linear-mcp save-issue --team "Engineering" --title "Implement feature" \
  --project "Q1 Roadmap" \
  --due-date "2024-03-15"

# Create sub-issue
linear-mcp save-issue --team "Engineering" --title "Subtask" \
  --parent-id "parent-issue-uuid"

# Create with links
linear-mcp save-issue --team "Engineering" --title "Fix bug" \
  --links '[{"url": "https://github.com/org/repo/pull/123", "title": "Fix PR"}]'

# Update state
linear-mcp save-issue --id "ABC-123" --state "Done"

# Reassign
linear-mcp save-issue --id "ABC-123" --assignee "jane@example.com"

# Update multiple fields
linear-mcp save-issue --id "ABC-123" \
  --state "In Progress" \
  --priority 1 \
  --labels '["urgent", "bug"]'

# Update description (write to file first, see "Content Preparation Workflow" above)
linear-mcp save-issue --id "ABC-123" \
  --arg-file description=<scratchpad>/issue-desc-UNIQUE.md
```

| Option | Description |
|--------|-------------|
| `--id` | Issue ID or identifier (e.g., `ABC-123`). If provided, updates; otherwise creates |
| `--team` | Team name or ID (required when creating) |
| `--title` | Issue title (required when creating) |
| `--description` | Markdown description |
| `--assignee` | User ID, name, email, or `"me"` |
| `--delegate` | Agent name or ID |
| `--state` | State type, name, or ID |
| `--priority` | 0-4 (see priority values) |
| `--estimate` | Issue estimate value |
| `--project` | Project name or ID |
| `--cycle` | Cycle name, number, or ID |
| `--milestone` | Milestone name or ID |
| `--labels` | JSON array of label names or IDs |
| `--due-date` | ISO date format |
| `--parent-id` | Parent issue ID or identifier (e.g., `ABC-123`). Null to remove |
| `--links` | JSON array of `{url, title}` objects. **Append-only** — existing links are never removed |

## Issue Relations

Create relationships between issues using identifiers (e.g., `ABC-123`) or UUIDs.

```bash
# Block other issues
linear-mcp save-issue --team "Eng" --title "Blocker" \
  --blocks '["ABC-123", "ABC-124"]'

# Blocked by other issues
linear-mcp save-issue --team "Eng" --title "Waiting" \
  --blocked-by '["ABC-100"]'

# Related issues
linear-mcp save-issue --team "Eng" --title "Related work" \
  --related-to '["ABC-50", "ABC-51"]'

# Mark as duplicate
linear-mcp save-issue --id "ABC-456" --duplicate-of "ABC-123"
```

**Append-only semantics:** `--blocks`, `--blocked-by`, `--related-to` (and `--links`) only ADD relations — they never remove existing ones. To remove relations, use the corresponding `--remove-blocks`, `--remove-blocked-by`, `--remove-related-to` parameters.

```bash
# Add a new blocker (existing blockers are preserved)
linear-mcp save-issue --id "ABC-123" --blocks '["DEF-456"]'

# Stop blocking a specific issue
linear-mcp save-issue --id "ABC-123" --remove-blocks '["DEF-456"]'

# Swap a blocker in one call
linear-mcp save-issue --id "ABC-123" \
  --remove-blocks '["DEF-123"]' \
  --blocks '["DEF-456"]'
```

**Note:** `--duplicate-of` is single-valued. To remove the duplicate relation, send a null: `linear-mcp save-issue --id "ABC-123" --input-json '{"duplicateOf": null}'`.
