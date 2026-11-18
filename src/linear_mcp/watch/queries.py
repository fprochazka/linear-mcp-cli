"""The GraphQL fragments and the paged follow-up queries of the watch."""

from __future__ import annotations

ISSUE_FIELDS = (
    "id identifier title url updatedAt createdAt archivedAt priority state { id name type } assignee { id name } "
    "delegate { id name } cycle { id number } project { id name } team { id key } labels { nodes { id name } } "
    "attachments(first: 25) { nodes { id title url sourceType } }"
)
COMMENT_FIELDS = (
    "id body createdAt updatedAt editedAt archivedAt resolvedAt parentId user { id name } botActor { name }"
)
HISTORY_FIELDS = (
    "id createdAt actor { id name } botActor { name } toStateId toAssigneeId addedLabelIds removedLabelIds attachmentId"
)
FRAGMENTS = {
    "I": f"fragment I on Issue {{ {ISSUE_FIELDS} }}\n",
    "C": f"fragment C on Comment {{ {COMMENT_FIELDS} }}\n",
    "H": f"fragment H on IssueHistory {{ {HISTORY_FIELDS} }}\n",
}


def with_fragments(query: str) -> str:
    """The query with the fragments it spreads, and no others: Linear refuses a document with an unused fragment."""
    used = [text for name, text in FRAGMENTS.items() if f"...{name} " in query or f"...{name}}}" in query]
    return "".join(used) + query


CHANGED = "{or: [{updatedAt: {gt: $S}}, {comments: {some: {updatedAt: {gt: $S}}}}]}"


def changed_issues(alias: str, filter_var: str, since_var: str, first: int) -> str:
    """Issues of a filter that changed, or got a comment changed, since a time; with those comments and history."""
    changed = CHANGED.replace("$S", f"${since_var}")
    return (
        f"{alias}: issues(filter: {{and: [${filter_var}, {changed}]}}, first: {first}, orderBy: updatedAt, "
        f"includeArchived: true) {{ nodes {{ ...I "
        f"comments(filter: {{updatedAt: {{gt: ${since_var}}}}}, first: 50, orderBy: updatedAt, includeArchived: true) "
        f"{{ nodes {{ ...C }} }} history(first: 10) {{ nodes {{ ...H }} }} }} pageInfo {{ hasNextPage endCursor }} }}"
    )


def watched_issues(alias: str, filter_var: str, since_var: str, first: int) -> str:
    """The issues of an issue watch, always, with the comments changed since a time and all comment ids."""
    return (
        f"{alias}: issues(filter: ${filter_var}, first: {first}, includeArchived: true) {{ nodes {{ ...I "
        f"comments(filter: {{updatedAt: {{gt: ${since_var}}}}}, first: 50, orderBy: updatedAt, includeArchived: true) "
        f"{{ nodes {{ ...C }} }} allComments: comments(first: 250) {{ nodes {{ id }} }} "
        f"history(first: 10) {{ nodes {{ ...H }} }} }} }}"
    )


TEAM = "{alias}: team(id: ${var}) {{ id key activeCycle {{ id number }} }}"
VIEW = "{alias}: customView(id: ${var}) {{ id slugId updatedAt filterData team {{ id key }} }}"

PAGE_ISSUES = with_fragments(
    "query Page($f: IssueFilter!, $after: String) { r: issues(filter: $f, first: 250, after: $after, "
    "includeArchived: false) { nodes { ...I } pageInfo { hasNextPage endCursor } } }"
)
PAGE_IDS = (
    "query Ids($f: IssueFilter!, $after: String) { r: issues(filter: $f, first: 250, after: $after) "
    "{ nodes { id } pageInfo { hasNextPage endCursor } } }"
)
PAGE_VIEW_IDS = (
    "query ViewIds($v: String!, $after: String) { r: customView(id: $v) { issues(first: 250, after: $after) "
    "{ nodes { id } pageInfo { hasNextPage endCursor } } } }"
)
PAGE_CHANGED = with_fragments(
    "query More($f: IssueFilter!, $s: DateTimeOrDuration!, $after: String) { r: issues(filter: {and: [$f, "
    + CHANGED.replace("$S", "$s")
    + "]}, first: 50, after: $after, orderBy: updatedAt, includeArchived: true) { nodes { ...I "
    "comments(filter: {updatedAt: {gt: $s}}, first: 50, orderBy: updatedAt, includeArchived: true) { nodes { ...C } } "
    "history(first: 10) { nodes { ...H } } } pageInfo { hasNextPage endCursor } } }"
)
VIEWER = "query { viewer { id name organization { urlKey } } }"
