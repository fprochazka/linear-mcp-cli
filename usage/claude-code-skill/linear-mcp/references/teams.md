# Teams Reference

## list_teams

List teams in the workspace.

```bash
# All teams
linear-mcp list_teams

# Search by name
linear-mcp list_teams --query "Engineering"

# Recently updated
linear-mcp list_teams --updatedAt "-P30D"
```

| Option | Description |
|--------|-------------|
| `--query` | Search in team name |
| `--createdAt`, `--updatedAt` | ISO-8601 or duration |
| `--limit` | Max results (default 50, max 250) |
| `--includeArchived` | Include archived teams |

## get_team

Get team details.

```bash
linear-mcp get_team --id "team-uuid"
```

**Note:** `--id` requires the internal UUID from `list_teams`.

## list_issue_statuses

List workflow statuses for a team. Statuses are team-specific.

```bash
linear-mcp list_issue_statuses --team "Engineering"
```

Returns statuses in workflow order: Backlog → Todo → In Progress → Done → Canceled.

**Note:** `--team` accepts team name or ID.

## get_issue_status

Get details of a specific issue status.

```bash
linear-mcp get_issue_status --team "Engineering" --name "In Progress"

# Or by ID
linear-mcp get_issue_status --team "Engineering" --id "status-uuid"
```

## list_cycles

List cycles (sprints) for a team.

```bash
# All cycles
linear-mcp list_cycles --teamId "team-uuid"

# Current cycle only
linear-mcp list_cycles --teamId "team-uuid" --type "current"

# Previous cycle
linear-mcp list_cycles --teamId "team-uuid" --type "previous"

# Next cycle
linear-mcp list_cycles --teamId "team-uuid" --type "next"
```

**Note:** `--teamId` requires the internal UUID from `list_teams`.

| Option | Description |
|--------|-------------|
| `--teamId` | Team UUID (required) |
| `--type` | `current`, `previous`, `next`, or omit for all |
