# Linear MCP CLI

A command-line interface for querying Linear using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server. Each Linear MCP tool is exposed as a direct CLI command.

## Features

- Direct CLI commands for each Linear MCP tool (issues, projects, teams, documents, etc.)
- Auto-generated parameters from MCP tool schemas with proper type handling
- 1-hour cache for tool schemas to speed up subsequent invocations
- Configuration via YAML file or environment variables
- Rich terminal output with JSON pretty-printing

## Installation

Requires Python 3.11+.

```bash
# Clone the repository
git clone <repo-url>
cd linear-mcp-cli

# Install with Poetry
poetry install

# Or install in development mode
pipx install -e .
```

## Claude Code Skill (Optional)

For users of Claude Code, a skill is available that teaches Claude how to efficiently use the `linear-mcp` CLI tool. The skill includes:

- Command reference for all Linear operations
- Common workflow examples for issues, projects, teams
- Parameter syntax (priority values, array formats)

### Installing the Skill

**For Claude Code (CLI)** - Global installation (available in all projects):

```bash
# Copy the skill directory to your global Claude Code skills directory
cp -r usage/claude-code-skill/linear-mcp ~/.claude/skills/
```

**For Claude Code (CLI)** - Project-specific installation (available only in this project):

```bash
# Copy the skill directory to your project's .claude/skills directory
mkdir -p .claude/skills
cp -r usage/claude-code-skill/linear-mcp .claude/skills/
```

**For Claude.ai or Claude Desktop** - Use the packaged skill file:

The `linear-mcp.skill` file can be uploaded through Settings > Capabilities > Skills.

After installation, Claude will automatically use the skill when working with Linear.

### Setting Default Permissions (Recommended)

To improve the Claude Code experience, you can configure default permissions for `linear-mcp` commands. This eliminates the need to approve these read-only commands every time.

Add the following to your `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Skill(linear-mcp)",
      "Bash(linear-mcp:*)"
    ]
  }
}
```

## Configuration

### Option 1: Interactive setup

```bash
linear-mcp init
```

This prompts for your credentials and saves them to `~/.config/linear-mcp/config.yaml`:

```
Linear MCP CLI Configuration

You can get your Linear API key from: https://linear.app/settings/api
Linear API Key: ********

Configuration saved to: ~/.config/linear-mcp/config.yaml
```

### Option 2: Environment variables

```bash
export LINEAR_API_KEY="your-api-key"
```

Environment variables take precedence over config file values.

## Usage

### List available commands

```bash
linear-mcp --help
```

### Get help for a specific command

```bash
linear-mcp create_issue --help
```

### Example commands

```bash
# List my issues
linear-mcp list_issues --assignee "me"

# List issues by state
linear-mcp list_issues --state "In Progress" --team "Engineering"

# Get issue details
linear-mcp get_issue --id "ABC-123"

# Create an issue
linear-mcp create_issue --team "Engineering" --title "Fix login bug" \
  --description "Users cannot log in with SSO"

# Update issue state
linear-mcp update_issue --id "ABC-123" --state "Done"

# Add a comment
linear-mcp create_comment --issue-id "ABC-123" --body "Fixed in PR #456"

# List projects
linear-mcp list_projects

# List teams
linear-mcp list_teams
```

### Output formats

By default, output is pretty-printed JSON. Use `--json` for raw JSON output:

```bash
linear-mcp list_issues --assignee "me" --json
```

### Show current configuration

```bash
linear-mcp config
```

## Available Commands

The CLI dynamically exposes all Linear MCP tools as commands:

| Command | Description |
|---------|-------------|
| `list_issues` | List issues (filter by assignee, state, team, project, label) |
| `get_issue` | Get issue details by ID |
| `create_issue` | Create a new issue |
| `update_issue` | Update an existing issue |
| `list_projects` | List projects |
| `get_project` | Get project details |
| `create_project` | Create a new project |
| `update_project` | Update an existing project |
| `list_teams` | List teams |
| `get_team` | Get team details |
| `list_users` | List users |
| `get_user` | Get user details |
| `list_documents` | List documents |
| `get_document` | Get document by ID/slug |
| `create_document` | Create a new document |
| `update_document` | Update a document |
| `list_comments` | List issue comments |
| `create_comment` | Add a comment to an issue |
| `list_issue_labels` | List issue labels |
| `create_issue_label` | Create a new label |
| `list_issue_statuses` | List issue statuses for a team |
| `get_issue_status` | Get issue status details |
| `list_project_labels` | List project labels |
| `list_cycles` | List cycles for a team |
| `search_documentation` | Search Linear documentation |

## Caching

Tool schemas are cached for 1 hour at `~/.cache/linear-mcp/` to speed up CLI startup. Delete the cache directory to force a refresh.

## Project Structure

```
src/linear_mcp/
├── __init__.py   # Package metadata
├── cache.py      # Tool schema caching
├── cli.py        # CLI with dynamic command generation
├── client.py     # MCP client with Bearer auth
└── config.py     # Configuration management
```

## Development

```bash
# Install dev dependencies
poetry install

# Run linter with auto-fix and formatter
source .venv/bin/activate && ruff check --fix . && ruff format .
```

## License

MIT
