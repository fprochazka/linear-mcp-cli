# Teams Reference

**Note:** `--team` accepts the team's name (e.g., `"Frontend Engineering"`), its key, which is the issue prefix (e.g., `"FE"`), or its ID. Run `list-teams` to find them.

## list-teams

List teams in the workspace.

```bash
# All teams
linear-mcp list-teams

# Search by name
linear-mcp list-teams --query "Engineering"

# Recently updated
linear-mcp list-teams --updated-at "-P30D"
```

| Option | Description |
|--------|-------------|
| `--query` | Search in team name |
| `--created-at`, `--updated-at` | ISO-8601 or duration |
| `--limit` | Max results (default 50, max 250) |
| `--include-archived` | Include archived teams |

## get-team

Get team details.

```bash
# By name
linear-mcp get-team --query "Engineering"

# By key
linear-mcp get-team --query "ENG"

# By UUID
linear-mcp get-team --query "team-uuid"
```

**Note:** `--query` accepts team name, key, or UUID.

## list-issue-statuses

List workflow statuses for a team. Statuses are team-specific.

```bash
linear-mcp list-issue-statuses --team "Engineering"
```

Returns statuses with their names, types and IDs. `list-issues --state` accepts any of them: a status name (e.g., `"In Progress"`, case-insensitive), a type (e.g., `"started"`, which matches every status of that type) or an ID.

**Note:** `--team` accepts the team name, key or ID.

## get-issue-status

Get details of a specific issue status. The tool requires `--id`, `--name` and `--team` together, so for a lookup by name use `list-issue-statuses --team` instead.

```bash
linear-mcp get-issue-status --team "Engineering" --name "In Progress" --id "status-uuid"
```

## list-cycles

List cycles (sprints) for a team.

```bash
# All cycles
linear-mcp list-cycles --team-id "team-uuid"

# Current cycle only
linear-mcp list-cycles --team-id "team-uuid" --type "current"

# Previous cycle
linear-mcp list-cycles --team-id "team-uuid" --type "previous"

# Next cycle
linear-mcp list-cycles --team-id "team-uuid" --type "next"
```

**Note:** `--team-id` requires the internal UUID from `list-teams`.

| Option | Description |
|--------|-------------|
| `--team-id` | Team UUID (required) |
| `--type` | `current`, `previous`, `next`, or omit for all |
