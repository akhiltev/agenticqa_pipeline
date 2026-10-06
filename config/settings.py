"""Central configuration for the Agentic QA Pipeline demo.

All settings are environment-driven (see .env.example). Nothing here should
contain secrets; secrets are read from the environment only (NFR-5).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root if present. Safe to call multiple times.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


@dataclass
class AzureOpenAISettings:
    endpoint: str = field(default_factory=lambda: _env("AZURE_OPENAI_ENDPOINT"))
    api_key: str = field(default_factory=lambda: _env("AZURE_OPENAI_API_KEY"))
    deployment: str = field(default_factory=lambda: _env("AZURE_OPENAI_DEPLOYMENT"))
    embedding_deployment: str = field(
        default_factory=lambda: _env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    )
    api_version: str = field(
        default_factory=lambda: _env("AZURE_OPENAI_API_VERSION", "2024-10-21")
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key and self.deployment)


@dataclass
class AzureDevOpsSettings:
    pat: str = field(default_factory=lambda: _env("AZURE_DEVOPS_PAT"))
    org: str = field(default_factory=lambda: _env("AZURE_DEVOPS_ORG"))
    project: str = field(default_factory=lambda: _env("AZURE_DEVOPS_PROJECT"))
    repo: str = field(default_factory=lambda: _env("AZURE_DEVOPS_REPO"))

    @property
    def is_configured(self) -> bool:
        return bool(self.pat and self.org and self.project)


@dataclass
class Settings:
    requirements_source: str = field(default_factory=lambda: _env("REQUIREMENTS_SOURCE", "mock"))
    pr_source: str = field(default_factory=lambda: _env("PR_SOURCE", "mock"))

    azure_openai: AzureOpenAISettings = field(default_factory=AzureOpenAISettings)
    azure_devops: AzureDevOpsSettings = field(default_factory=AzureDevOpsSettings)

    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    sut_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "sut")
    graphify_out_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "sut" / "graphify-out")
    specs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "specs")
    fixtures_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "fixtures")
    reports_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "reports")
    chroma_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "rag" / "chroma_store")
    maven_home: Path = field(
        default_factory=lambda: PROJECT_ROOT / "tools" / "apache-maven-3.9.16"
    )
    java_home: str = field(default_factory=lambda: _env("JAVA_HOME"))

    # Iteration bounds (NFR-6)
    max_plan_generate_iterations: int = field(
        default_factory=lambda: _env_int("MAX_PLAN_GENERATE_ITERATIONS", 3)
    )
    max_guardrail_retries: int = field(
        default_factory=lambda: _env_int("MAX_GUARDRAIL_RETRIES", 2)
    )
    coverage_target_pct: float = field(
        default_factory=lambda: float(_env("COVERAGE_TARGET_PCT", "80"))
    )

    def ensure_dirs(self) -> None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

    def build_openai_client(self):
        """Builds an OpenAI-compatible client for this project's Azure
        endpoint (chat + embeddings).

        NOTE (validated 2026-09-04): the Azure AI Foundry-style resource used
        for this demo (`*.services.ai.azure.com`) does not use the classic
        dated `api-version` + `/openai/deployments/{name}` routing that the
        SDK's `AzureOpenAI` client assumes - it uses the unified
        `{endpoint}/openai/v1/...` surface instead, with the API key sent as
        an `api-key` header (not `Authorization: Bearer`). Using the plain
        `OpenAI` client pointed at that base_url is what actually works
        against this resource; classic `*.openai.azure.com` /
        `*.cognitiveservices.azure.com` resources using the dated
        api-version scheme would instead need `AzureOpenAI(...)`.
        """
        from openai import OpenAI

        cfg = self.azure_openai
        return OpenAI(
            base_url=cfg.endpoint.rstrip("/") + "/openai/v1",
            api_key=cfg.api_key,
            default_headers={"api-key": cfg.api_key},
        )


settings = Settings()
