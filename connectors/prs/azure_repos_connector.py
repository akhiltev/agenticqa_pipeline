"""Real Azure Repos connector (FR-12).

Authenticates using the same Azure DevOps PAT as AzureBoardsConnector and
fetches PR diffs / posts PR comments via the Azure DevOps Git REST API.
"""
from __future__ import annotations

import base64
import logging

import requests

from config.settings import settings

from .base import FileDiff, PRConnector, PullRequest

logger = logging.getLogger(__name__)

API_VERSION = "7.1"


class AzureReposConnector(PRConnector):
    def __init__(self) -> None:
        cfg = settings.azure_devops
        if not cfg.is_configured or not cfg.repo:
            raise RuntimeError(
                "AzureReposConnector requires AZURE_DEVOPS_PAT, AZURE_DEVOPS_ORG, "
                "AZURE_DEVOPS_PROJECT and AZURE_DEVOPS_REPO to be set."
            )
        self._org = cfg.org
        self._project = cfg.project
        self._repo = cfg.repo
        token = base64.b64encode(f":{cfg.pat}".encode("utf-8")).decode("utf-8")
        self._headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }
        self._base_url = (
            f"https://dev.azure.com/{self._org}/{self._project}/_apis/git/"
            f"repositories/{self._repo}"
        )

    def _get_pr(self, pr_id: str) -> dict | None:
        url = f"{self._base_url}/pullrequests/{pr_id}?api-version={API_VERSION}"
        resp = requests.get(url, headers=self._headers, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def _get_diff(self, pr: dict) -> list[FileDiff]:
        pr_id = pr["pullRequestId"]
        last_iteration = pr.get("lastMergeSourceCommit", {})
        url = (
            f"{self._base_url}/pullrequests/{pr_id}/iterations"
            f"?api-version={API_VERSION}"
        )
        resp = requests.get(url, headers=self._headers, timeout=30)
        resp.raise_for_status()
        iterations = resp.json().get("value", [])
        if not iterations:
            return []
        last_it_id = iterations[-1]["id"]
        changes_url = (
            f"{self._base_url}/pullrequests/{pr_id}/iterations/{last_it_id}"
            f"/changes?api-version={API_VERSION}"
        )
        resp = requests.get(changes_url, headers=self._headers, timeout=30)
        resp.raise_for_status()
        files: list[FileDiff] = []
        for change in resp.json().get("changeEntries", []):
            item = change.get("item", {})
            path = item.get("path", "")
            change_type = change.get("changeType", "edit")
            if not path:
                continue
            # Full content diff computation is left for follow-up; this
            # captures path + change type which is sufficient for scoping
            # Planner/Graphify queries in PR mode (FR-3, FR-14).
            files.append(FileDiff(path=path, change_type=change_type, diff_text=""))
        return files

    def fetch_pr(self, pr_id: str) -> PullRequest | None:
        raw = self._get_pr(pr_id)
        if raw is None:
            return None
        return self._to_pull_request(raw, self._get_diff(raw))

    def fetch_open_prs(self) -> list[PullRequest]:
        url = f"{self._base_url}/pullrequests?searchCriteria.status=active&api-version={API_VERSION}"
        resp = requests.get(url, headers=self._headers, timeout=30)
        resp.raise_for_status()
        return [
            self._to_pull_request(raw, self._get_diff(raw))
            for raw in resp.json().get("value", [])
        ]

    def post_comment(self, pr_id: str, text: str) -> None:
        url = f"{self._base_url}/pullrequests/{pr_id}/threads?api-version={API_VERSION}"
        payload = {"comments": [{"parentCommentId": 0, "content": text, "commentType": 1}]}
        resp = requests.post(url, headers=self._headers, json=payload, timeout=30)
        resp.raise_for_status()

    @staticmethod
    def _to_pull_request(raw: dict, files: list[FileDiff]) -> PullRequest:
        return PullRequest(
            id=str(raw.get("pullRequestId")),
            title=raw.get("title", ""),
            description=raw.get("description", "") or "",
            source_branch=raw.get("sourceRefName", ""),
            target_branch=raw.get("targetRefName", ""),
            files=files,
            linked_work_item_ids=[
                str(w.get("id")) for w in raw.get("workItemRefs", [])
            ],
            source="azure_repos",
        )
