"""RAG indexing (FR-6): embeds normalized requirement chunks (and static
specs/) into a local Chroma vector store.

When Azure OpenAI is not configured (NFR-1: offline-runnable demo), falls
back to a deterministic local hash-based embedding so the rest of the
pipeline plumbing can still be exercised without live API calls.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import chromadb
from chromadb import EmbeddingFunction

from config.settings import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "requirements"
_HASH_DIM = 384


class _HashEmbeddingFunction(EmbeddingFunction):
    """Deterministic offline fallback embedding (NFR-1).

    Not semantically meaningful, but stable and dependency-free - lets the
    RAG plumbing (index/query round trip) be exercised without any external
    API calls when Azure OpenAI credentials are not supplied.
    """

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        vectors = []
        for text in input:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            # Repeat/truncate the 32-byte digest to a fixed-size float vector.
            raw = (digest * (_HASH_DIM // len(digest) + 1))[:_HASH_DIM]
            vectors.append([b / 255.0 for b in raw])
        return vectors

    @staticmethod
    def name() -> str:
        return "offline_hash_embedding"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "_HashEmbeddingFunction":
        return _HashEmbeddingFunction()



class _AzureOpenAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self) -> None:
        cfg = settings.azure_openai
        self._client = settings.build_openai_client()
        self._deployment = cfg.embedding_deployment
        # Eagerly probe the embeddings deployment so misconfiguration (e.g. no
        # deployment by this name on the resource - a real gap we hit while
        # validating this demo's Azure OpenAI setup) is caught here and
        # triggers the offline fallback in _get_embedding_function(), instead
        # of surfacing as a hard crash mid-pipeline the first time a document
        # is actually embedded.
        self._client.embeddings.create(model=self._deployment, input=["__probe__"])

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        resp = self._client.embeddings.create(model=self._deployment, input=input)
        return [item.embedding for item in resp.data]


    @staticmethod
    def name() -> str:
        return "azure_openai_embedding"

    def get_config(self) -> dict:
        return {"deployment": self._deployment}

    @staticmethod
    def build_from_config(config: dict) -> "_AzureOpenAIEmbeddingFunction":
        return _AzureOpenAIEmbeddingFunction()



def _get_embedding_function():
    if settings.azure_openai.is_configured:
        try:
            return _AzureOpenAIEmbeddingFunction()
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to initialize Azure OpenAI embeddings; falling back to "
                "offline hash embedding."
            )
    else:
        logger.info(
            "Azure OpenAI not configured; using offline hash embedding for RAG "
            "(NFR-1). Set AZURE_OPENAI_* env vars for real semantic retrieval."
        )
    return _HashEmbeddingFunction()


def get_chroma_collection():
    settings.ensure_dirs()
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_get_embedding_function(),
    )


def index_requirement_items(items) -> int:
    """Upserts normalized requirement items into Chroma (FR-6). Returns count indexed."""
    if not items:
        return 0
    collection = get_chroma_collection()
    collection.upsert(
        ids=[f"{item.source}:{item.id}" for item in items],
        documents=[item.to_chunk_text() for item in items],
        metadatas=[
            {"source": item.source, "item_id": item.id, "title": item.title}
            for item in items
        ],
    )
    return len(items)


def index_spec_files(specs_dir: Path | None = None) -> int:
    """Indexes static markdown spec files from specs/ (spec mode, FR-24)."""
    specs_dir = specs_dir or settings.specs_dir
    if not specs_dir.exists():
        return 0
    files = sorted(specs_dir.glob("*.md"))
    if not files:
        return 0
    collection = get_chroma_collection()
    collection.upsert(
        ids=[f"spec:{f.name}" for f in files],
        documents=[f.read_text(encoding="utf-8") for f in files],
        metadatas=[{"source": "spec", "item_id": f.stem, "title": f.stem} for f in files],
    )
    return len(files)


def query_requirements(question: str, n_results: int = 4) -> list[dict]:
    """Semantic retrieval of requirement/spec chunks relevant to `question`."""
    collection = get_chroma_collection()
    if collection.count() == 0:
        return []
    n_results = min(n_results, collection.count())
    result = collection.query(query_texts=[question], n_results=n_results)
    hits = []
    for doc, meta, dist in zip(
        result.get("documents", [[]])[0],
        result.get("metadatas", [[]])[0],
        result.get("distances", [[]])[0],
    ):
        hits.append({"document": doc, "metadata": meta, "distance": dist})
    return hits
