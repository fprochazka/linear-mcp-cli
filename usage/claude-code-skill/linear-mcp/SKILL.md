---
name: linear-mcp
description: CLI for querying Linear (issues, projects, teams, documents, comments). Use when managing issues, creating/updating tasks, exploring projects, or integrating Linear with workflows. Triggered by requests involving Linear data, issue tracking, or project management.
---

# Linear MCP CLI

Direct CLI access to Linear data. Each Linear MCP tool is exposed as a command.

## Commands

| Command | Description |
|---------|-------------|
| `list_issues` | List issues (filter by assignee, state, team, project, label) |
| `get_issue` | Get issue details by ID |
| `create_issue` | Create issue (requires team, title) |
| `update_issue` | Update issue (state, assignee, labels, etc.) |
| `list_projects` | List projects |
| `get_project` | Get project details |
| `create_project` | Create project |
| `update_project` | Update project |
| `list_teams` | List teams |
| `get_team` | Get team details |
| `list_users` | List users (optionally filter by team) |
| `get_user` | Get user details |
| `list_documents` | List documents |
| `get_document` | Get document by ID/slug |
| `create_document` | Create document |
| `update_document` | Update document |
| `list_comments` | List issue comments |
| `create_comment` | Add comment to issue |
| `list_issue_labels` | List labels (optionally by team) |
| `create_issue_label` | Create label |
| `list_issue_statuses` | List statuses for team |
| `list_project_labels` | List project labels |
| `list_cycles` | List cycles for team |
| `search_documentation` | Search Linear docs |

## Common Examples

### Issues

```bash
# List my issues
linear-mcp list_issues --assignee "me"

# Filter by state/team
linear-mcp list_issues --state "In Progress" --team "Engineering"

# Get issue details
linear-mcp get_issue --id "ABC-123"

# Create issue
linear-mcp create_issue --team "Engineering" --title "Fix login bug" \
  --description "Users cannot log in with SSO" --assignee "me" --priority 2

# Update issue
linear-mcp update_issue --id "ABC-123" --state "Done"

# Add comment
linear-mcp create_comment --issue-id "ABC-123" --body "Fixed in PR #456"
```

### Projects

```bash
linear-mcp list_projects
linear-mcp get_project --query "Q1 Roadmap"
linear-mcp create_project --name "Q2 Roadmap" --team "Engineering"
linear-mcp update_project --id "PROJECT-ID" --state "completed"
```

### Teams & Users

```bash
linear-mcp list_teams
linear-mcp list_users --team "Engineering"
```

### Labels & Statuses

```bash
linear-mcp list_issue_labels --team "Engineering"
linear-mcp list_issue_statuses --team "Engineering"
linear-mcp create_issue_label --name "critical" --team "Engineering" --color "#FF0000"
```

## Key Parameters

### Priority Values

| Value | Meaning |
|-------|---------|
| `0` | No priority |
| `1` | Urgent |
| `2` | High |
| `3` | Normal |
| `4` | Low |

### Array Syntax

Pass arrays as JSON strings:

```bash
--labels '["bug", "critical"]'
--links '[{"url": "https://github.com/...", "title": "PR"}]'
```

### Assignee

Use `"me"` for current user or email/user ID.

## Help

Run `linear-mcp <command> --help` for full options.

Use `--json` flag for raw JSON output.
