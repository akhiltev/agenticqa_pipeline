"""Mock requirements connector (FR-7). Default connector for the demo -
requires no external accounts or credentials.
"""
from __future__ import annotations

import json

from config.settings import settings

from .base import RequirementItem, RequirementsConnector


class MockRequirementsConnector(RequirementsConnector):
    def __init__(self, fixture_path=None) -> None:
        self._fixture_path = fixture_path or (settings.fixtures_dir / "work_items.json")

    def _load(self) -> list[dict]:
        with open(self._fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("work_items", [])

    def fetch_items(self) -> list[RequirementItem]:
        return [
            RequirementItem(
                id=item["id"],
                title=item["title"],
                description=item["description"],
                acceptance_criteria=item.get("acceptance_criteria", ""),
                tags=item.get("tags", []),
                links=item.get("links", []),
                source="mock",
            )
            for item in self._load()
        ]

    def fetch_item(self, item_id: str) -> RequirementItem | None:
        for item in self.fetch_items():
            if item.id == item_id:
                return item
        return None
