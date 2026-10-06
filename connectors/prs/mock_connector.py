"""Mock PR connector (FR-11). Default connector for the demo - requires no
external accounts or credentials.
"""
from __future__ import annotations

import json
import logging

from config.settings import settings

from .base import FileDiff, PRConnector, PullRequest

logger = logging.getLogger(__name__)


class MockPRConnector(PRConnector):
    def __init__(self, fixture_path=None) -> None:
        self._fixture_path = fixture_path or (settings.fixtures_dir / "sample_pr.json")

    def _load(self) -> dict:
        with open(self._fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def fetch_pr(self, pr_id: str) -> PullRequest | None:
        data = self._load()
        if data.get("id") != pr_id and pr_id not in (None, "", data.get("id")):
            # Only one fixture PR is available; return it regardless of the
            # requested id if it doesn't match, but log a notice.
            logger.info(
                "Mock PR connector only has fixture '%s'; ignoring requested id '%s'.",
                data.get("id"),
                pr_id,
            )
        return self._to_pull_request(data)

    def fetch_open_prs(self) -> list[PullRequest]:
        return [self._to_pull_request(self._load())]

    def post_comment(self, pr_id: str, text: str) -> None:
        logger.info("[mock PR comment] PR %s:\n%s", pr_id, text)

    @staticmethod
    def _to_pull_request(data: dict) -> PullRequest:
        return PullRequest(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            source_branch=data["source_branch"],
            target_branch=data["target_branch"],
            files=[
                FileDiff(
                    path=f["path"],
                    change_type=f["change_type"],
                    diff_text=f["diff_text"],
                )
                for f in data.get("files", [])
            ],
            linked_work_item_ids=data.get("linked_work_item_ids", []),
            source="mock",
        )
