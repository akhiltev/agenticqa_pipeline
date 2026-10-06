"""Factory: selects a requirements connector implementation based on
REQUIREMENTS_SOURCE config, with no code changes required elsewhere (NFR-3).
"""
from __future__ import annotations

from config.settings import settings

from .base import RequirementsConnector


def get_requirements_connector() -> RequirementsConnector:
    source = settings.requirements_source.lower()
    if source == "mock":
        from .mock_connector import MockRequirementsConnector

        return MockRequirementsConnector()
    if source == "azure_boards":
        from .azure_boards_connector import AzureBoardsConnector

        return AzureBoardsConnector()
    if source == "jira":
        from .jira_connector import JiraConnector

        return JiraConnector()
    raise ValueError(f"Unknown REQUIREMENTS_SOURCE: {source!r}")
