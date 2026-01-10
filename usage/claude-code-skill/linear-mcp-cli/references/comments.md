# Comments Reference

## list_comments

List comments for an issue.

```bash
linear-mcp list_comments --issueId "issue-uuid"
```

**Note:** `--issueId` requires the internal UUID from `list_issues` or `get_issue`.

## create_comment

Add a comment to an issue.

```bash
# Write comment to file first, then use $(cat ...) - see "Content Preparation Workflow" in SKILL.md
linear-mcp create_comment --issueId "issue-uuid" \
  --body "$(cat /tmp/comment.md)"

# Reply to existing comment
linear-mcp create_comment --issueId "issue-uuid" \
  --parentId "comment-uuid" \
  --body "$(cat /tmp/reply.md)"
```

| Option | Description |
|--------|-------------|
| `--issueId` | Issue UUID (required) |
| `--body` | Comment content as Markdown (required) |
| `--parentId` | Parent comment UUID (for replies) |

**Note:** Both `--issueId` and `--parentId` require internal UUIDs.
