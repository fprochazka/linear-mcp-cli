# Documents Reference

## list-documents

List documents in the workspace.

```bash
# All documents
linear-mcp list-documents

# Search by content
linear-mcp list-documents --query "roadmap"

# By project
linear-mcp list-documents --project-id "project-uuid"

# Recently updated
linear-mcp list-documents --updated-at "-P7D"
```

| Option | Description |
|--------|-------------|
| `--query` | Search query |
| `--project-id` | Project UUID |
| `--initiative-id` | Initiative UUID |
| `--creator-id` | Creator UUID |
| `--created-at`, `--updated-at` | ISO-8601 or duration |
| `--limit` | Max results (default 50, max 250) |
| `--include-archived` | Include archived documents |

**Note:** Filter IDs (`--project-id`, `--initiative-id`, `--creator-id`) require internal UUIDs.

## get-document

Get document content by ID or slug.

```bash
# By ID
linear-mcp get-document --id "document-uuid"

# By slug
linear-mcp get-document --id "my-document-slug"
```

## save-document

Create or update a document. If `--id` is provided, updates the existing document; otherwise creates a new one. When creating, `--title` and exactly one parent (`--project`, `--issue`, `--initiative`, or `--cycle`) are required. On update, passing a parent reparents the document.

```bash
# Create basic (no content)
linear-mcp save-document --title "Meeting Notes" --project "Engineering"

# Create with content (write to file first, see "Content Preparation Workflow" in SKILL.md)
linear-mcp save-document --title "Architecture Decision" \
  --project "Backend Refactor" \
  --arg-file content=<scratchpad>/doc-arch-decision-UNIQUE.md

# Attached to an issue
linear-mcp save-document --title "Investigation Notes" \
  --issue "ABC-123" \
  --arg-file content=<scratchpad>/doc-investigation-UNIQUE.md

# With icon and color
linear-mcp save-document --title "Team Handbook" \
  --project "Engineering" \
  --icon ":book:" \
  --color "#10B981"

# Update content (write to file first)
linear-mcp save-document --id "document-uuid" \
  --arg-file content=<scratchpad>/doc-update-UNIQUE.md

# Update title
linear-mcp save-document --id "document-uuid" --title "New Title"

# Reparent to a different project
linear-mcp save-document --id "document-uuid" --project "New Project"
```

| Option | Description |
|--------|-------------|
| `--id` | Document ID or slug. If provided, updates; otherwise creates |
| `--title` | Document title (required when creating) |
| `--project` | Project name, ID, or slug (parent) |
| `--issue` | Issue ID or identifier, e.g., `ABC-123` (parent) |
| `--initiative` | Initiative name or ID (parent) |
| `--cycle` | Cycle name, number, or ID (parent). Pair with `--team` to disambiguate names/numbers |
| `--team` | Team name or ID. Only used to resolve `--cycle` |
| `--content` | Markdown content |
| `--icon` | Emoji (e.g., `:page_facing_up:`) |
| `--color` | Icon hex color |

**Note:** Exactly one parent (`--project`, `--issue`, `--initiative`, or `--cycle`) is required when creating.
