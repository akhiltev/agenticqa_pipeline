"""Common interface + normalized schema for PR connectors.

Implements FR-9/FR-10: PR_SOURCE selects an implementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class FileDiff:
    path: str
    change_type: str  # "add" | "edit" | "delete"
    diff_text: str


@dataclass
class PullRequest:
    """Normalized PR schema used across all PR connectors (FR-10)."""

    id: str
    title: str
    description: str
    source_branch: str
    target_branch: str
    files: list[FileDiff] = field(default_factory=list)
    linked_work_item_ids: list[str] = field(default_factory=list)
    source: str = "unknown"

    def changed_file_paths(self) -> list[str]:
        return [f.path for f in self.files]


class PRConnector(ABC):
    """Interface all PR connectors must implement (FR-10)."""

    @abstractmethod
    def fetch_pr(self, pr_id: str) -> PullRequest | None:
        """Fetch a single PR (with diff) by ID, or None if not found."""

    @abstractmethod
    def fetch_open_prs(self) -> list[PullRequest]:
        """Fetch all open PRs (diff optional; used for `continuous` mode)."""

    @abstractmethod
    def post_comment(self, pr_id: str, text: str) -> None:
        """Post a QA summary comment on the given PR."""
