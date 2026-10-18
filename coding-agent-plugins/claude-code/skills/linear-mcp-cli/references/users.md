# Users Reference

## list-users

List users in the workspace.

```bash
# All users
linear-mcp list-users

# Filter by team
linear-mcp list-users --team "Engineering"

# Search by name or email
linear-mcp list-users --query "john"
```

| Option | Description |
|--------|-------------|
| `--team` | Team name or ID |
| `--query` | Search by name or email |

## get-user

Get user details.

```bash
# By name
linear-mcp get-user --query "John Doe"

# By email
linear-mcp get-user --query "john@example.com"

# Current user
linear-mcp get-user --query "me"
```

**Note:** `--query` accepts user ID, name, email, or `"me"`.
