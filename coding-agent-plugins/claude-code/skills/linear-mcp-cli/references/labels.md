# Labels Reference

Labels can be scoped to a workspace (available to all teams) or a specific team.

## list-issue-labels

List available issue labels.

```bash
# All labels (workspace + all teams)
linear-mcp list-issue-labels

# Labels for a specific team
linear-mcp list-issue-labels --team "Engineering"

# Filter by name
linear-mcp list-issue-labels --name "bug"
```

| Option | Description |
|--------|-------------|
| `--team` | Team name or ID |
| `--name` | Filter by label name |
| `--limit` | Max results (default 50, max 250) |

## save-issue-label

Create or update an issue label. If `--id` is provided (label name or ID), updates the existing label; otherwise creates a new one.

```bash
# Workspace-level label (available to all teams)
linear-mcp save-issue-label --name "critical" --color "#FF0000"

# Team-specific label
linear-mcp save-issue-label --name "frontend" --team-id "team-uuid" --color "#3B82F6"

# With description
linear-mcp save-issue-label --name "needs-review" \
  --description "Issues requiring code review" \
  --color "#F59E0B"

# Create a label group (cannot be applied directly to issues)
linear-mcp save-issue-label --name "Priority" --is-group

# Child label in a group
linear-mcp save-issue-label --name "P0" --parent "Priority" --color "#EF4444"
```

| Option | Description |
|--------|-------------|
| `--id` | Label name or ID. If provided, updates the existing label |
| `--name` | Label name (required when creating) |
| `--color` | Hex color code |
| `--description` | Label description |
| `--team-id` | Team UUID (omit for workspace label) |
| `--parent` | Parent label group name or ID |
| `--is-group` | Create as label group (default false) |

**Note:** `--team-id` requires an internal UUID.
