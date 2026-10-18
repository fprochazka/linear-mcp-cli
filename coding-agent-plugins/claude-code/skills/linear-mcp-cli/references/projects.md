# Projects Reference

## list-projects

List projects in the workspace.

```bash
# All projects
linear-mcp list-projects

# By team
linear-mcp list-projects --team "Engineering"

# By state
linear-mcp list-projects --state "started"

# My projects
linear-mcp list-projects --member "me"

# Search by name
linear-mcp list-projects --query "Q1"

# Recently updated
linear-mcp list-projects --updated-at "-P7D"
```

| Option | Description |
|--------|-------------|
| `--team` | Team name or ID |
| `--state` | State name or ID |
| `--initiative` | Initiative name or ID |
| `--member` | User ID, name, email, or `"me"` |
| `--query` | Search in project name |
| `--created-at`, `--updated-at` | ISO-8601 or duration |
| `--limit` | Max results (default 50, max 250) |
| `--include-archived` | Include archived projects |

## get-project

Get project details.

```bash
# By name
linear-mcp get-project --query "Q1 Roadmap"

# By ID
linear-mcp get-project --query "project-uuid"
```

**Note:** `--query` accepts project name, ID, or slug.

## save-project

Create or update a project. If `--id` is provided, updates the existing project; otherwise creates a new one. When creating, `--name` and at least one team (via `--add-teams` or `--set-teams`) are required.

```bash
# Create basic
linear-mcp save-project --name "Q2 Roadmap" --add-teams "Engineering"

# Create with description (write to file first, see "Content Preparation Workflow" in SKILL.md)
linear-mcp save-project --name "Q2 Roadmap" --add-teams "Engineering" \
  --arg-file description=<scratchpad>/project-desc-UNIQUE.md \
  --summary "Q2 engineering initiatives" \
  --lead "me" \
  --priority 2

# Create with dates
linear-mcp save-project --name "Q2 Roadmap" --add-teams "Engineering" \
  --start-date "2024-04-01" \
  --target-date "2024-06-30"

# Create with multiple teams and labels
linear-mcp save-project --name "Mobile App" \
  --set-teams "Engineering" --set-teams "Mobile" \
  --icon ":iphone:" \
  --color "#FF5733" \
  --labels '["mobile", "priority"]'

# Update state
linear-mcp save-project --id "project-uuid" --state "completed"

# Update lead
linear-mcp save-project --id "project-uuid" --lead "jane@example.com"

# Update dates
linear-mcp save-project --id "project-uuid" \
  --target-date "2024-07-15"

# Update description (write to file first, see "Content Preparation Workflow" in SKILL.md)
linear-mcp save-project --id "project-uuid" \
  --arg-file description=<scratchpad>/project-desc-UNIQUE.md

# Add/remove a team on an existing project
linear-mcp save-project --id "project-uuid" --add-teams "Design"
linear-mcp save-project --id "project-uuid" --remove-teams "Design"

# Link/unlink initiatives
linear-mcp save-project --id "project-uuid" --add-initiatives "Q2 Goals"
linear-mcp save-project --id "project-uuid" --remove-initiatives "Q2 Goals"
```

| Option | Description |
|--------|-------------|
| `--id` | Project ID. If provided, updates; otherwise creates |
| `--name` | Project name (required when creating) |
| `--add-teams` | Team name or ID to add. At least one team via `--add-teams` or `--set-teams` is required when creating |
| `--remove-teams` | Team name or ID to remove |
| `--set-teams` | Replace all teams with these. Cannot combine with `--add-teams`/`--remove-teams` |
| `--description` | Full Markdown description |
| `--summary` | Plaintext summary (max 255 chars) |
| `--lead` | User ID, name, email, or `"me"`. Null to remove |
| `--priority` | 0-4 (see priority values) |
| `--state` | Project state |
| `--add-initiatives` | Initiative name or ID to add |
| `--remove-initiatives` | Initiative name or ID to remove |
| `--set-initiatives` | Replace all initiatives with these. Cannot combine with `--add-initiatives`/`--remove-initiatives` |
| `--start-date`, `--target-date` | ISO date format |
| `--start-date-resolution`, `--target-date-resolution` | Date precision (e.g., `month`, `quarter`) |
| `--icon` | Emoji (e.g., `:eagle:`) |
| `--color` | Hex color code |
| `--labels` | Label names or IDs |

## list-project-labels

List labels available for projects.

```bash
linear-mcp list-project-labels

# Filter by name
linear-mcp list-project-labels --name "priority"
```
