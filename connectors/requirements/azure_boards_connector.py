"""Real Azure Boards connector (FR-8).

Authenticates via a Personal Access Token (PAT) and fetches work items using
the Azure DevOps WIQL + Work Items REST API (api-version 7.1).
"""
from __future__ import annotations

import base64
import logging

import requests

from config.settings import settings

from .base import RequirementItem, RequirementsConnector

logger = logging.getLogger(__name__)

API_VERSION = "7.1"


class AzureBoardsConnector(RequirementsConnector):
    def __init__(self) -> None:
        cfg = settings.azure_devops
        if not cfg.is_configured:
            raise RuntimeError(
                "AzureBoardsConnector requires AZURE_DEVOPS_PAT, AZURE_DEVOPS_ORG "
                "and AZURE_DEVOPS_PROJECT to be set."
            )
        self._org = cfg.org
        self._project = cfg.project
        token = base64.b64encode(f":{cfg.pat}".encode("utf-8")).decode("utf-8")
        self._headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }
        self._base_url = f"https://dev.azure.com/{self._org}/{self._project}/_apis"

    def _wiql_query(self, wiql: str) -> list[int]:
        url = f"{self._base_url}/wit/wiql?api-version={API_VERSION}"
        resp = requests.post(url, headers=self._headers, json={"query": wiql}, timeout=30)
        resp.raise_for_status()
        return [wi["id"] for wi in resp.json().get("workItems", [])]

    def _get_work_items(self, ids: list[int]) -> list[dict]:
        if not ids:
            return []
        ids_param = ",".join(str(i) for i in ids)
        url = (
            f"{self._base_url}/wit/workitems?ids={ids_param}"
            f"&$expand=all&api-version={API_VERSION}"
        )
        resp = requests.get(url, headers=self._headers, timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])

    @staticmethod
    def _to_requirement_item(raw: dict) -> RequirementItem:
        fields = raw.get("fields", {})
        return RequirementItem(
            id=str(raw.get("id")),
            title=fields.get("System.Title", ""),
            description=fields.get("System.Description", "") or "",
            acceptance_criteria=fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "") or "",
            tags=[t.strip() for t in (fields.get("System.Tags") or "").split(";") if t.strip()],
            links=[str(r.get("url", "")) for r in raw.get("relations", [])],
            source="azure_boards",
        )

    def fetch_items(self) -> list[RequirementItem]:
        wiql = (
            "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = "
            f"'{self._project}' ORDER BY [System.ChangedDate] DESC"
        )
        ids = self._wiql_query(wiql)
        return [self._to_requirement_item(raw) for raw in self._get_work_items(ids)]

    def fetch_item(self, item_id: str) -> RequirementItem | None:
        raws = self._get_work_items([int(item_id)])
        if not raws:
            return None
        return self._to_requirement_item(raws[0])
