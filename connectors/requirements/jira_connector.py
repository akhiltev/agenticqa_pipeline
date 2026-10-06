"""Documented stub for a future Jira Cloud connector (NFR-4).

TODO(follow-up): Implement using the Jira Cloud REST API v3
(https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/),
authenticating via an API token + email (Basic auth) or OAuth 2.0.
Expected mapping:
  - fetch_items(): JQL search (e.g. `project = X ORDER BY updated DESC`)
    against `/rest/api/3/search`, normalizing `fields.summary` -> title,
    `fields.description` (Atlassian Document Format) -> description, and any
    custom "Acceptance Criteria" field -> acceptance_criteria.
  - fetch_item(item_id): `/rest/api/3/issue/{item_id}`.
Configuration should follow the same pattern as AzureBoardsConnector: read
JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN / JIRA_PROJECT_KEY from settings.
"""
from __future__ import annotations

from .base import RequirementItem, RequirementsConnector


class JiraConnector(RequirementsConnector):
    def __init__(self) -> None:
        raise NotImplementedError(
            "JiraConnector is a documented stub. See module docstring for the "
            "expected implementation using the Jira Cloud REST API v3."
        )

    def fetch_items(self) -> list[RequirementItem]:
        raise NotImplementedError

    def fetch_item(self, item_id: str) -> RequirementItem | None:
        raise NotImplementedError
