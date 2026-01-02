# Users Reference

## list_users

List users in the workspace.

```bash
# All users
linear-mcp list_users

# Filter by team
linear-mcp list_users --team "Engineering"

# Search by name or email
linear-mcp list_users --query "john"
```

| Option | Description |
|--------|-------------|
| `--team` | Team name or ID |
| `--query` | Search by name or email |

## get_user

Get user details.

```bash
linear-mcp get_user --id "user-uuid"
```

**Note:** `--id` requires the internal UUID from `list_users`.
