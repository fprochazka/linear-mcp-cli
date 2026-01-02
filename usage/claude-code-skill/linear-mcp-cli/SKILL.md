---
name: linear-mcp-cli
description: CLI for querying Linear (issues, projects, teams, documents, comments). Use when managing issues, creating/updating tasks, exploring projects, or integrating Linear with workflows. Triggered by requests involving Linear data, issue tracking, or project management.
---

# Linear MCP CLI

CLI tool providing direct access to Linear data. Each Linear MCP tool is exposed as a command.

## Quick Reference

| Entity | Commands | Reference |
|--------|----------|-----------|
| **Issues** | `list_issues`, `get_issue`, `create_issue`, `update_issue` | [issues.md](references/issues.md) |
| **Projects** | `list_projects`, `get_project`, `create_project`, `update_project`, `list_project_labels` | [projects.md](references/projects.md) |
| **Teams** | `list_teams`, `get_team`, `list_issue_statuses`, `get_issue_status`, `list_cycles` | [teams.md](references/teams.md) |
| **Users** | `list_users`, `get_user` | [users.md](references/users.md) |
| **Labels** | `list_issue_labels`, `create_issue_label` | [labels.md](references/labels.md) |
| **Documents** | `list_documents`, `get_document`, `create_document`, `update_document` | [documents.md](references/documents.md) |
| **Comments** | `list_comments`, `create_comment` | [comments.md](references/comments.md) |
| **Docs** | `search_documentation` | [docs.md](references/docs.md) |

## Parameter Resolution

Most parameters accept human-readable names. The MCP server resolves them to internal IDs.

| Parameter | Accepts | Example |
|-----------|---------|---------|
| `--team`, `--project`, `--state`, `--cycle`, `--milestone`, `--label`, `--initiative` | **Exact full name** (case-insensitive) or ID | `--team "Engineering"` |
| `--assignee`, `--member`, `--lead` | User ID, name, email, or `"me"` | `--assignee "me"` |
| `--labels` (array) | Names or IDs | `'["bug", "critical"]'` |

**Important: Use exact full names, not abbreviations or partial matches.**

| Filter | Works | Doesn't work |
|--------|-------|--------------|
| `--team` | `"Frontend Engineering"` (full name) | `"FE"` (issue prefix) |
| `--project` | `"API Redesign (Q1 2025)"` (full name) | `"API Redesign"` (partial) |
| `--state` | `"In Progress"` (status name) | `"started"` (status type) |

To find correct names, first run `list_teams`, `list_projects`, or `list_issue_statuses --team "Team Name"`.

**Internal UUID required** (from prior `list_*` or `get_*` calls):

| Parameter | Context |
|-----------|---------|
| `--id` | `get_issue`, `update_issue`, `update_project`, `update_document` |
| `--issueId` | `list_comments`, `create_comment` |
| `--teamId` | `list_cycles`, `create_issue_label` |
| `--parentId` | Sub-issues, child labels |
| `--projectId`, `--initiativeId`, `--creatorId` | `list_documents` filters |

**Issue references** (for relations):

| Parameter | Accepts |
|-----------|---------|
| `--blocks`, `--blockedBy`, `--relatedTo`, `--duplicateOf` | Issue ID or identifier (e.g., `'["ABC-123"]'`) |

## Array Syntax

Pass arrays as JSON strings:

```bash
--labels '["bug", "critical"]'
--links '[{"url": "https://github.com/...", "title": "PR"}]'
```

## Priority Values

| Value | Issue | Project |
|-------|-------|---------|
| `0` | No priority | No priority |
| `1` | Urgent | Urgent |
| `2` | High | High |
| `3` | Normal | Medium |
| `4` | Low | Low |

## Getting Command Help

```bash
linear-mcp <command> --help
```
