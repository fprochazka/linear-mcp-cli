# Documents Reference

## list_documents

List documents in the workspace.

```bash
# All documents
linear-mcp list_documents

# Search by content
linear-mcp list_documents --query "roadmap"

# By project
linear-mcp list_documents --projectId "project-uuid"

# Recently updated
linear-mcp list_documents --updatedAt "-P7D"
```

| Option | Description |
|--------|-------------|
| `--query` | Search query |
| `--projectId` | Project UUID |
| `--initiativeId` | Initiative UUID |
| `--creatorId` | Creator UUID |
| `--createdAt`, `--updatedAt` | ISO-8601 or duration |
| `--limit` | Max results (default 50, max 250) |
| `--includeArchived` | Include archived documents |

**Note:** Filter IDs (`--projectId`, `--initiativeId`, `--creatorId`) require internal UUIDs.

## get_document

Get document content by ID or slug.

```bash
# By ID
linear-mcp get_document --id "document-uuid"

# By slug
linear-mcp get_document --id "my-document-slug"
```

## create_document

Create a new document.

```bash
# Basic
linear-mcp create_document --title "Meeting Notes" --project "Engineering"

# With content
linear-mcp create_document --title "Architecture Decision" \
  --project "Backend Refactor" \
  --content "# ADR-001\n\n## Context\n\n..."

# With icon
linear-mcp create_document --title "Team Handbook" \
  --project "Engineering" \
  --icon ":book:" \
  --color "#10B981"
```

| Option | Description |
|--------|-------------|
| `--title` | Document title (required) |
| `--project` | Project name or ID (required) |
| `--content` | Markdown content |
| `--icon` | Emoji (e.g., `:page_facing_up:`) |
| `--color` | Icon hex color |

## update_document

Update an existing document.

```bash
# Update content
linear-mcp update_document --id "document-uuid" \
  --content "# Updated content\n\n..."

# Update title
linear-mcp update_document --id "document-uuid" --title "New Title"

# Move to different project
linear-mcp update_document --id "document-uuid" --project "New Project"
```

**Note:** `--id` requires the internal UUID from `list_documents` or `get_document`.
