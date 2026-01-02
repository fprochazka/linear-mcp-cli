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
# Basic comment
linear-mcp create_comment --issueId "issue-uuid" --body "Looking into this now."

# Markdown comment
linear-mcp create_comment --issueId "issue-uuid" \
  --body "Fixed in PR #123.\n\n**Changes:**\n- Updated auth flow\n- Added tests"

# Reply to existing comment
linear-mcp create_comment --issueId "issue-uuid" \
  --parentId "comment-uuid" \
  --body "Good point, I'll address that."
```

| Option | Description |
|--------|-------------|
| `--issueId` | Issue UUID (required) |
| `--body` | Comment content as Markdown (required) |
| `--parentId` | Parent comment UUID (for replies) |

**Note:** Both `--issueId` and `--parentId` require internal UUIDs.
