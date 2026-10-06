"""Factory: selects a PR connector implementation based on PR_SOURCE
config, with no code changes required elsewhere (NFR-3).
"""
from __future__ import annotations

from config.settings import settings

from .base import PRConnector


def get_pr_connector() -> PRConnector:
    source = settings.pr_source.lower()
    if source == "mock":
        from .mock_connector import MockPRConnector

        return MockPRConnector()
    if source == "azure_repos":
        from .azure_repos_connector import AzureReposConnector

        return AzureReposConnector()
    if source == "github":
        from .github_connector import GitHubConnector

        return GitHubConnector()
    raise ValueError(f"Unknown PR_SOURCE: {source!r}")
