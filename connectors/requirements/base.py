"""Common interface + normalized schema for requirements connectors.

Implements FR-4/FR-5: REQUIREMENTS_SOURCE selects an implementation; all
implementations normalize output into RequirementItem for RAG indexing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RequirementItem:
    """Normalized requirement/work-item schema used for RAG indexing (FR-5)."""

    id: str
    title: str
    description: str
    acceptance_criteria: str = ""
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    source: str = "unknown"

    def to_chunk_text(self) -> str:
        """Renders this item as a single text chunk suitable for embedding."""
        parts = [f"# {self.id}: {self.title}", "", self.description]
        if self.acceptance_criteria:
            parts += ["", "## Acceptance Criteria", self.acceptance_criteria]
        if self.tags:
            parts += ["", f"Tags: {', '.join(self.tags)}"]
        return "\n".join(parts)


class RequirementsConnector(ABC):
    """Interface all requirements connectors must implement (FR-5)."""

    @abstractmethod
    def fetch_items(self) -> list[RequirementItem]:
        """Fetch all available requirement items."""

    @abstractmethod
    def fetch_item(self, item_id: str) -> RequirementItem | None:
        """Fetch a single requirement item by ID, or None if not found."""
