# Linear MCP CLI

A command-line interface for [Linear](https://linear.app) through its official [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server at `https://mcp.linear.app/mcp`. Each tool of the server (issues, projects, teams, documents, comments, labels, cycles, ...) is a command.

Built on [mcp-to-cli-kit](https://pypi.org/project/mcp-to-cli-kit/), which turns every MCP tool into a subcommand with typed options compiled from the tool's input schema.

## Installation

Requires Python 3.11+ and uv. The kit comes from PyPI as a regular dependency.

```bash
git clone https://github.com/fprochazka/linear-mcp-cli.git
cd linear-mcp-cli

# Install globally (editable - updates after git pull)
uv tool install -e .
```

## Configuration

The CLI needs a Linear API key, which you create at https://linear.app/settings/api. Either export it:

```bash
export LINEAR_API_KEY="lin_api_..."
```

or put it in `~/.config/linear-mcp/config.yaml` (or a file passed with `--config PATH`); keep that file readable by you only (`chmod 600`):

```yaml
servers:
  linear:
    headers:
      Authorization: "Bearer lin_api_..."
```

The built-in default sends `Authorization: Bearer ${LINEAR_API_KEY}`, with the variable expanded when the server is contacted. An `Authorization` header in the file replaces that template, so the file wins over the variable. Without either, a command that contacts Linear exits 2 and names the variable; `--help` still works from the tool cache.

Other keys and their environment variables:

```yaml
servers:
  linear:
    timeout: 30            # seconds to connect and to send a request
    sse_read_timeout: 100  # seconds to wait for an answer
```

```bash
export LINEAR_MCP_SERVERS__LINEAR__SSE_READ_TIMEOUT=200
```

`linear-mcp config` prints the effective configuration without contacting Linear, with the key masked.

## Usage

```bash
linear-mcp --help                                  # the tools
linear-mcp get-issue --help                        # one tool's full description and options
linear-mcp schema get-issue                        # the tool's raw input schema

linear-mcp list-teams
linear-mcp list-issue-statuses --team "<team name or id>"
linear-mcp list-issues --assignee me --limit 10
linear-mcp list-issues --team "<team>" --state "In Progress" --order-by updatedAt
linear-mcp get-issue --id ABC-123 --include-relations
linear-mcp list-projects --limit 5
linear-mcp get-user --query me
```

- Commands are kebab case (`get-issue`). The tool's own name (`get_issue`) still works.
- Options are kebab case (`--include-relations`). The schema's own spelling (`--includeRelations`) and the snake case are accepted too.
- An option you leave out is not sent; the server applies its default. Booleans are `--x` / `--no-x`. Arrays are repeated options or one JSON literal; objects take a JSON literal.
- `--input-json` passes all arguments as one JSON object; `--arg-file NAME=PATH` reads one value from a file, which suits long Markdown bodies (`--arg-file body=comment.md`).
- Under an AI agent, or with `--json`, the result is printed exactly as the server sent it. Otherwise, or with `--pretty`, JSON is indented. Several content items become one JSON array.
- Exit codes: 0 success, 1 the tool reported an error, 2 a usage or config error, 3 the server could not be reached.
- The tool list is cached for an hour in `~/.cache/linear-mcp/linear.json`; `--refresh-tools` fetches it again. `-v` and `-vv` log to stderr, with the key redacted.

The `save_*`, `delete_*`, `create_*`, `retire_*`, `restore_*`, `mark_*`, `share_*` and `unshare_*` tools change your Linear workspace.

## Changes from the previous version

- The config shape changed. The old `linear.api_key` and `mcp_server:` keys are gone; a config file that still uses them fails with "linear: Extra inputs are not permitted" (exit 2). Put the key into `servers.linear.headers.Authorization` as `Bearer <key>`, as shown above. The old environment overrides `LINEAR_MCP_LINEAR__API_KEY`, `LINEAR_MCP_MCP_SERVER__TIMEOUT` and `LINEAR_MCP_MCP_SERVER__SSE_READ_TIMEOUT` are ignored too; use `LINEAR_API_KEY` and `LINEAR_MCP_SERVERS__LINEAR__TIMEOUT` / `LINEAR_MCP_SERVERS__LINEAR__SSE_READ_TIMEOUT` (or any other `LINEAR_MCP_SERVERS__LINEAR__*` key). With `-v` the CLI lists the variables it ignored.
- An `Authorization` header in the config file now wins over `LINEAR_API_KEY`; before, the variable won.
- `linear-mcp init` is gone. Create the file by hand or export `LINEAR_API_KEY`.
- `linear-mcp config` prints JSON (with the key masked) instead of a rich panel, and also shows the config file, the env prefix and the env variables that were applied.
- `./.linear-mcp.yaml` in the working directory is no longer read. Pass it with `--config` instead.
- `-c` for `--config` is gone. `-v` now logs to stderr instead of showing tracebacks.
- Commands are kebab case (`get-issue`) and options too (`--include-relations`). The old spellings (`get_issue`, `--includeRelations`) still work.
- Booleans are `--x` / `--no-x`; the old `--x true` / `--x false` form is rejected. This affects every `--include*` option and `--hasReleaseNotes`, `--isDiffHidden`, `--isGroup`, `--isProduction`, `--read`, `--shared` and `--unreadOnly`.
- Output is plain JSON without rich, so it never wraps and pipes into `jq`. Defaults from the schemas are no longer sent.
- Exit codes: usage and config errors exit 2 and an unreachable server exits 3. Previously every error exited 1.
- The default read timeout is 100 s instead of 300 s, so a slow call ends before an agent's 120 s Bash limit. Raise it with `LINEAR_MCP_SERVERS__LINEAR__SSE_READ_TIMEOUT` or the `servers.linear.sse_read_timeout` config key.
- The old tool cache `~/.cache/linear-mcp/tools.json` is no longer used and can be deleted; the new one is `~/.cache/linear-mcp/linear.json`.

## Claude Code skill

The repo is also a Claude Code plugin marketplace (`fprochazka-linear-mcp-cli`) with one plugin, `linear-mcp-cli`. Its skill teaches an agent the commands for issues, projects, teams, users, labels, documents and comments, how names resolve to IDs, how to pass long Markdown bodies from files, and how to avoid creating duplicates.

```bash
claude plugin marketplace add https://github.com/fprochazka/linear-mcp-cli.git
claude plugin install linear-mcp-cli@fprochazka-linear-mcp-cli
```

If you copied the skill by hand before (`~/.claude/skills/linear-mcp-cli`), remove that copy once the plugin is installed; otherwise Claude loads two skills with the same name.

The skill allows the read-only commands without a prompt: every `get-*`, `list-*` and `search-*` command, `schema`, `config` (which masks the key) and `--help`. Of the commands that change your workspace, only the `--help` of `save-issue`, `save-comment`, `save-document`, `save-project` and `save-issue-label` is allowed; running them asks for permission. The granted read commands also accept `--arg-file` and `--input-json @file`, so an agent can send the content of a local file to Linear (as a search query or filter) without a prompt.

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src tests && uv run pytest
```

To develop against a local checkout of the kit, run `uv pip install -e <path-to-mcp-to-cli-kit>` after `uv sync`; the next `uv sync` restores the PyPI release.

## License

MIT
