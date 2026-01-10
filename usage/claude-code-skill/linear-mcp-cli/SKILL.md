---
name: linear-mcp-cli
description: CLI for querying Linear (issues, projects, teams, documents, comments). Use when managing issues, creating/updating tasks, exploring projects, or integrating Linear with workflows. Triggered by requests involving Linear data, issue tracking, or project management.
trigger-keywords: linear, issue, issues, tasks, task, ticket, tickets
---

# Linear MCP CLI

CLI tool providing direct access to Linear data. Each Linear MCP tool is exposed as a command.

## Quick Reference

| Entity | Commands | Reference |
|--------|----------|-----------|
| **Issues** | `list_issues`, `get_issue`, `create_issue`, `update_issue` | *(below)* |
| **Projects** | `list_projects`, `get_project`, `create_project`, `update_project`, `list_project_labels` | [projects.md](references/projects.md) |
| **Teams** | `list_teams`, `get_team`, `list_issue_statuses`, `get_issue_status`, `list_cycles` | [teams.md](references/teams.md) |
| **Users** | `list_users`, `get_user` | [users.md](references/users.md) |
| **Labels** | `list_issue_labels`, `create_issue_label` | [labels.md](references/labels.md) |
| **Documents** | `list_documents`, `get_document`, `create_document`, `update_document` | [documents.md](references/documents.md) |
| **Comments** | `list_comments`, `create_comment` | [comments.md](references/comments.md) |
| **Docs** | `search_documentation` | [docs.md](references/docs.md) |

## Parameter Resolution

Most parameters accept human-readable names. The MCP server resolves them to internal IDs.

| Parameter | Accepts | Example |
|-----------|---------|---------|
| `--team`, `--project`, `--state`, `--cycle`, `--milestone`, `--label`, `--initiative` | **Exact full name** (case-insensitive) or ID | `--team "Engineering"` |
| `--assignee`, `--member`, `--lead` | User ID, name, email, or `"me"` | `--assignee "me"` |
| `--labels` (array) | Names or IDs | `'["bug", "critical"]'` |

**Important: Use exact full names, not abbreviations or partial matches.**

| Filter | Works | Doesn't work |
|--------|-------|--------------|
| `--team` | `"Frontend Engineering"` (full name) | `"FE"` (issue prefix) |
| `--project` | `"API Redesign (Q1 2025)"` (full name) | `"API Redesign"` (partial) |
| `--state` | `"In Progress"` (status name) | `"started"` (status type) |

To find correct names, first run `list_teams`, `list_projects`, or `list_issue_statuses --team "Team Name"`.

**Internal UUID required** (from prior `list_*` or `get_*` calls):

| Parameter | Context |
|-----------|---------|
| `--id` | `get_issue`, `update_issue`, `update_project`, `update_document` |
| `--issueId` | `list_comments`, `create_comment` |
| `--teamId` | `list_cycles`, `create_issue_label` |
| `--parentId` | Sub-issues, child labels |
| `--projectId`, `--initiativeId`, `--creatorId` | `list_documents` filters |

**Issue references** (for relations):

| Parameter | Accepts |
|-----------|---------|
| `--blocks`, `--blockedBy`, `--relatedTo`, `--duplicateOf` | Issue ID or identifier (e.g., `'["ABC-123"]'`) |

## Array Syntax

Pass arrays as JSON strings:

```bash
--labels '["bug", "critical"]'
--links '[{"url": "https://github.com/...", "title": "PR"}]'
```

## Priority Values

| Value | Issue | Project |
|-------|-------|---------|
| `0` | No priority | No priority |
| `1` | Urgent | Urgent |
| `2` | High | High |
| `3` | Normal | Medium |
| `4` | Low | Low |

## Content Preparation Workflow (REQUIRED for long content)

**For multi-line or markdown content (descriptions, comments, documents), you MUST:**

1. **Write content to a markdown file first** (e.g., `/tmp/content.md`)
2. **Use `$(cat file.md)` to pass it to the CLI**

This prevents shell escaping issues, preserves formatting, and allows user review before submission.

| Parameter | Example |
|-----------|---------|
| `--description` | `--description "$(cat /tmp/desc.md)"` |
| `--body` | `--body "$(cat /tmp/comment.md)"` |
| `--content` | `--content "$(cat /tmp/doc.md)"` |

**Short, single-line values** (titles, names, summaries) can be passed directly as strings.

**DO NOT pass multi-line content or markdown directly as string arguments.**

## Getting Command Help

```bash
linear-mcp <command> --help
```

---

# Issues Reference

## list_issues

List issues in the workspace with filters.

```bash
# My issues
linear-mcp list_issues --assignee "me"

# Filter by state and team
linear-mcp list_issues --state "In Progress" --team "Engineering"

# By project
linear-mcp list_issues --project "Q1 Roadmap"

# Recently updated
linear-mcp list_issues --updatedAt "-P1D"

# Combine filters
linear-mcp list_issues --team "Engineering" --state "In Progress" --assignee "me" --limit 25
```

| Option | Description |
|--------|-------------|
| `--assignee` | User ID, name, email, or `"me"` |
| `--team` | **Exact** team name or ID (not issue prefix abbreviations) |
| `--state` | **Exact** status name or ID (not types like "started") |
| `--project` | **Exact** project name or ID (partial names don't work) |
| `--cycle` | Cycle name or ID |
| `--label` | Label name or ID |
| `--query` | Search in title/description |
| `--parentId` | Parent issue UUID (for sub-issues) |
| `--createdAt`, `--updatedAt` | ISO-8601 or duration (e.g., `-P1D`) |
| `--limit` | Max results (default 50, max 250) |
| `--includeArchived` | Include archived issues (default true) |

## get_issue

Get detailed issue info including attachments and git branch name.

```bash
linear-mcp get_issue --id "ABC-123"

# Include relations (blocking, related, duplicate)
linear-mcp get_issue --id "ABC-123" --includeRelations true
```

**Note:** `--id` accepts either the internal UUID or the issue identifier (e.g., `ABC-123`).

## create_issue

Create a new issue.

```bash
# Basic (no description)
linear-mcp create_issue --team "Engineering" --title "Fix login bug"

# With description (write to file first, see "Content Preparation Workflow" above)
linear-mcp create_issue --team "Engineering" --title "Fix login bug" \
  --description "$(cat /tmp/issue-description.md)" \
  --assignee "me" \
  --priority 2 \
  --state "To Do" \
  --labels '["bug", "auth"]'

# With project and due date
linear-mcp create_issue --team "Engineering" --title "Implement feature" \
  --project "Q1 Roadmap" \
  --dueDate "2024-03-15"

# Sub-issue
linear-mcp create_issue --team "Engineering" --title "Subtask" \
  --parentId "parent-issue-uuid"

# With links
linear-mcp create_issue --team "Engineering" --title "Fix bug" \
  --links '[{"url": "https://github.com/org/repo/pull/123", "title": "Fix PR"}]'
```

| Option | Description |
|--------|-------------|
| `--team` | Team name or ID (required) |
| `--title` | Issue title (required) |
| `--description` | Markdown description |
| `--assignee` | User ID, name, email, or `"me"` |
| `--state` | State type, name, or ID |
| `--priority` | 0-4 (see priority values) |
| `--project` | Project name or ID |
| `--cycle` | Cycle name, number, or ID |
| `--milestone` | Milestone name or ID |
| `--labels` | JSON array of label names or IDs |
| `--dueDate` | ISO date format |
| `--parentId` | Parent issue UUID |
| `--links` | JSON array of `{url, title}` objects |

## update_issue

Update an existing issue.

```bash
# Change state
linear-mcp update_issue --id "ABC-123" --state "Done"

# Reassign
linear-mcp update_issue --id "ABC-123" --assignee "jane@example.com"

# Update multiple fields
linear-mcp update_issue --id "ABC-123" \
  --state "In Progress" \
  --priority 1 \
  --labels '["urgent", "bug"]'

# Update description (write to file first, see "Content Preparation Workflow" above)
linear-mcp update_issue --id "ABC-123" \
  --description "$(cat /tmp/issue-description.md)"
```

**Note:** `--id` accepts either the internal UUID or the issue identifier (e.g., `ABC-123`).

## Issue Relations

Create relationships between issues using identifiers (e.g., `ABC-123`) or UUIDs.

```bash
# Block other issues
linear-mcp create_issue --team "Eng" --title "Blocker" \
  --blocks '["ABC-123", "ABC-124"]'

# Blocked by other issues
linear-mcp create_issue --team "Eng" --title "Waiting" \
  --blockedBy '["ABC-100"]'

# Related issues
linear-mcp create_issue --team "Eng" --title "Related work" \
  --relatedTo '["ABC-50", "ABC-51"]'

# Mark as duplicate
linear-mcp update_issue --id "ABC-456" --duplicateOf "ABC-123"
```

**WARNING for update_issue:** Relation arrays REPLACE all existing relations. Include ALL issues you want in the relation, not just new ones. Omit the parameter entirely to leave existing relations unchanged.

```bash
# WRONG: This removes existing blocks and only keeps DEF-456
linear-mcp update_issue --id "ABC-123" --blocks '["DEF-456"]'

# RIGHT: Include all issues that should block
linear-mcp update_issue --id "ABC-123" --blocks '["DEF-123", "DEF-456"]'

# RIGHT: Omit to leave unchanged
linear-mcp update_issue --id "ABC-123" --state "Done"
```
