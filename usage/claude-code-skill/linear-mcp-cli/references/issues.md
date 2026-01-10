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

# With description (write to file first, see "Content Preparation Workflow" in SKILL.md)
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

# Update description (write to file first, see "Content Preparation Workflow" in SKILL.md)
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
