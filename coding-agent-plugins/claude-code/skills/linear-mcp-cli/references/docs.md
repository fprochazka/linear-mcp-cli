# Documentation Reference

## search-documentation

Search Linear's official documentation.

```bash
# Search for workflow info
linear-mcp search-documentation --query "workflow states"

# Search for integration docs
linear-mcp search-documentation --query "github integration"

# Search for API info
linear-mcp search-documentation --query "webhooks"
```

| Option | Description |
|--------|-------------|
| `--query` | Search query (required) |
| `--page` | Page number for pagination (default 0) |

Returns documentation snippets with title, URL, and relevant content.
