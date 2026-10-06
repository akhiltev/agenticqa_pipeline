"""Validation script for Azure OpenAI settings (chat + embeddings).

Run: .venv\\Scripts\\python.exe validate_azure_openai.py
Does NOT print the API key. Exits non-zero on failure.

Uses settings.build_openai_client() (see config/settings.py), which builds
an OpenAI-compatible client pointed at {endpoint}/openai/v1 with the API key
sent as an `api-key` header. This is what actually works against Azure AI
Foundry-style resources (`*.services.ai.azure.com`), which don't use the
classic dated `api-version` + `/openai/deployments/{name}` routing that the
`openai` SDK's `AzureOpenAI` client assumes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings  # noqa: E402


def mask(s: str, keep: int = 4) -> str:
    if not s:
        return "(empty)"
    return s[:keep] + "..." + s[-keep:] if len(s) > keep * 2 else "***"


def main() -> int:
    cfg = settings.azure_openai
    print("=== Config (from .env) ===")
    print("AZURE_OPENAI_ENDPOINT      :", cfg.endpoint or "(empty)")
    print("AZURE_OPENAI_API_KEY       :", mask(cfg.api_key))
    print("AZURE_OPENAI_DEPLOYMENT    :", cfg.deployment or "(empty)")
    print("AZURE_OPENAI_EMBEDDING_DEP :", cfg.embedding_deployment or "(empty)")
    print("AZURE_OPENAI_API_VERSION   :", cfg.api_version or "(empty, unused by build_openai_client)")
    print("is_configured              :", cfg.is_configured)
    print()

    if not cfg.is_configured:
        print("FAIL: endpoint/api_key/deployment not all set.")
        return 1

    client = settings.build_openai_client()

    ok = True

    print("=== Chat completion test (deployment: %s) ===" % cfg.deployment)
    try:
        resp = client.chat.completions.create(
            model=cfg.deployment,
            messages=[{"role": "user", "content": "Reply with exactly: PING_OK"}],
            max_completion_tokens=20,
        )
        text = resp.choices[0].message.content
        print("Response:", text)
        print("PASS: chat completion succeeded.")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print("FAIL: chat completion error ->", repr(exc))

    print()
    print("=== Embeddings test (deployment: %s) ===" % cfg.embedding_deployment)
    try:
        resp = client.embeddings.create(
            model=cfg.embedding_deployment, input=["hello world"]
        )
        vec = resp.data[0].embedding
        print(f"Got embedding vector of length {len(vec)}.")
        print("PASS: embeddings call succeeded.")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print("FAIL: embeddings error ->", repr(exc))
        print(
            "NOTE: RAG (rag/index_specs.py) automatically falls back to an "
            "offline hash embedding if this fails (NFR-1), so the pipeline "
            "still runs - but semantic retrieval won't be meaningful until "
            "an embedding model is actually deployed under this name on "
            "the Azure resource."
        )

    print()
    print("=== RESULT:", "ALL PASS" if ok else "SOME FAILED", "===")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
