# Comments Reference

## list-comments

List comments for an issue.

```bash
# By issue identifier
linear-mcp list-comments --issue-id "ABC-123"

# Or by issue UUID
linear-mcp list-comments --issue-id "issue-uuid"
```

**Note:** `--issue-id` accepts the issue identifier (e.g., `ABC-123`) or the internal UUID.

## save-comment

Create or update a comment on an issue. If `--id` is provided, updates the existing comment; otherwise creates a new one.

```bash
# Create a new top-level comment (write to file first, see "Content Preparation Workflow" in SKILL.md)
linear-mcp save-comment --issue-id "ABC-123" \
  --arg-file body=<scratchpad>/comment-ABC-123.md

# Reply to an existing comment (thread)
linear-mcp save-comment --issue-id "ABC-123" \
  --parent-id "comment-uuid" \
  --arg-file body=<scratchpad>/comment-reply-ABC-123.md

# Update an existing comment
linear-mcp save-comment --id "comment-uuid" \
  --arg-file body=<scratchpad>/comment-edit-ABC-123.md
```

| Option | Description |
|--------|-------------|
| `--id` | Comment ID. If provided, updates the existing comment |
| `--issue-id` | Issue ID or identifier (e.g., `ABC-123`). Required when creating a new top-level comment |
| `--parent-id` | Parent comment UUID (for replies, only when creating) |
| `--body` | Comment content as Markdown (required) |

**Note:** `save-comment` can also target projects, initiatives, documents, and project milestones (via `--project-id`, `--initiative-id`, `--document-id`, `--milestone-id`) — see `linear-mcp save-comment --help`.
