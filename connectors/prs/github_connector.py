"""Documented stub for a future GitHub PR connector (NFR-4).

TODO(follow-up): Implement using the GitHub REST API
(https://docs.github.com/en/rest/pulls/pulls), authenticating via a
personal access token (Bearer auth). Expected mapping:
  - fetch_pr(pr_id): GET /repos/{owner}/{repo}/pulls/{pr_id} for metadata,
    GET /repos/{owner}/{repo}/pulls/{pr_id}/files for the diff (per-file
    `patch` field maps to FileDiff.diff_text). Linked work items can be
    parsed from PR body text (e.g. "Closes PROJ-123") since GitHub has no
    native work-item linkage.
  - fetch_open_prs(): GET /repos/{owner}/{repo}/pulls?state=open.
  - post_comment(pr_id, text): POST /repos/{owner}/{repo}/issues/{pr_id}/comments.
Configuration should follow the same pattern as AzureReposConnector: read
GITHUB_TOKEN / GITHUB_OWNER / GITHUB_REPO from settings.
"""
from __future__ import annotations

from .base import PRConnector, PullRequest


class GitHubConnector(PRConnector):
    def __init__(self) -> None:
        raise NotImplementedError(
            "GitHubConnector is a documented stub. See module docstring for "
            "the expected implementation using the GitHub REST API."
        )

    def fetch_pr(self, pr_id: str) -> PullRequest | None:
        raise NotImplementedError

    def fetch_open_prs(self) -> list[PullRequest]:
        raise NotImplementedError

    def post_comment(self, pr_id: str, text: str) -> None:
        raise NotImplementedError
