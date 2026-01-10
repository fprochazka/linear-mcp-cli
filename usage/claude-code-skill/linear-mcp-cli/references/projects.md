# Projects Reference

## list_projects

List projects in the workspace.

```bash
# All projects
linear-mcp list_projects

# By team
linear-mcp list_projects --team "Engineering"

# By state
linear-mcp list_projects --state "started"

# My projects
linear-mcp list_projects --member "me"

# Search by name
linear-mcp list_projects --query "Q1"

# Recently updated
linear-mcp list_projects --updatedAt "-P7D"
```

| Option | Description |
|--------|-------------|
| `--team` | Team name or ID |
| `--state` | State name or ID |
| `--initiative` | Initiative name or ID |
| `--member` | User ID, name, email, or `"me"` |
| `--query` | Search in project name |
| `--createdAt`, `--updatedAt` | ISO-8601 or duration |
| `--limit` | Max results (default 50, max 250) |
| `--includeArchived` | Include archived projects |

## get_project

Get project details.

```bash
# By name
linear-mcp get_project --query "Q1 Roadmap"

# By ID
linear-mcp get_project --query "project-uuid"
```

**Note:** `--query` accepts either project name or ID.

## create_project

Create a new project.

```bash
# Basic
linear-mcp create_project --team "Engineering" --name "Q2 Roadmap"

# With description (write to file first, see "Content Preparation Workflow" in SKILL.md)
linear-mcp create_project --team "Engineering" --name "Q2 Roadmap" \
  --description "$(cat /tmp/project-description.md)" \
  --summary "Q2 engineering initiatives" \
  --lead "me" \
  --priority 2

# With dates
linear-mcp create_project --team "Engineering" --name "Q2 Roadmap" \
  --startDate "2024-04-01" \
  --targetDate "2024-06-30"

# With labels and icon
linear-mcp create_project --team "Engineering" --name "Mobile App" \
  --icon ":iphone:" \
  --color "#FF5733" \
  --labels '["mobile", "priority"]'
```

| Option | Description |
|--------|-------------|
| `--team` | Team name or ID (required) |
| `--name` | Project name (required) |
| `--description` | Full Markdown description |
| `--summary` | Plaintext summary (max 255 chars) |
| `--lead` | User ID, name, email, or `"me"` |
| `--priority` | 0-4 (see priority values) |
| `--state` | Project state |
| `--initiative` | Initiative name or ID |
| `--startDate`, `--targetDate` | ISO date format |
| `--icon` | Emoji (e.g., `:eagle:`) |
| `--color` | Hex color code |
| `--labels` | JSON array of label names or IDs |

## update_project

Update an existing project.

```bash
# Change state
linear-mcp update_project --id "project-uuid" --state "completed"

# Update lead
linear-mcp update_project --id "project-uuid" --lead "jane@example.com"

# Update dates
linear-mcp update_project --id "project-uuid" \
  --targetDate "2024-07-15"

# Update description (write to file first, see "Content Preparation Workflow" in SKILL.md)
linear-mcp update_project --id "project-uuid" \
  --description "$(cat /tmp/project-description.md)"
```

**Note:** `--id` requires the internal UUID from `list_projects` or `get_project`.

## list_project_labels

List labels available for projects.

```bash
linear-mcp list_project_labels

# Filter by name
linear-mcp list_project_labels --name "priority"
```
