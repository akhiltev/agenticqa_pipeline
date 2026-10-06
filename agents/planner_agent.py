"""Planner Agent (FR-13, FR-14): combines Graphify structural context with
RAG-retrieved requirement/spec chunks to produce a ranked list of test
targets. Runs as an A2A server exposing a single skill via message/send.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.a2a_common import build_agent_app, build_agent_card  # noqa: E402
from config.settings import settings  # noqa: E402
from mcp_servers import graphify_mcp_server as graphify_tools  # noqa: E402
from rag.index_specs import query_requirements  # noqa: E402

logger = logging.getLogger(__name__)

AGENT_URL = "http://127.0.0.1:8801/"


def _rank_targets(
    candidate_files: list[str],
    requirement_hits: list[dict],
    target_class: str | None = None,
) -> list[dict]:
    """Heuristic ranking: prioritizes candidate nodes whose source_file
    appears in the PR diff (FR-14) and whose label/file loosely matches the
    retrieved requirement text; falls back to graph fan-in (# of edges) as a
    proxy for "important, so worth testing" when no PR context is given.

    If `target_class` is given, only nodes belonging to that class's source
    file are considered at all (a deterministic override for demos, bypassing
    ranking - see REQUIREMENTS.md section 6a: without real embeddings
    deployed, RAG retrieval is not semantically meaningful, so ranking
    otherwise tends to fall back to structural fan-in and keeps re-selecting
    high-fan-in "god nodes" like CDL regardless of the actual question).
    """
    graph = graphify_tools._load_graph()
    nodes = [n for n in graph.get("nodes", []) if n.get("file_type") == "code"]

    if target_class:
        target_lower = target_class.lower()
        nodes = [
            n
            for n in nodes
            if target_lower in n.get("source_file", "").lower()
            or target_lower == n.get("label", "").strip(".()").lower()
        ]

    def touches_changed_files(node: dict) -> bool:
        if not candidate_files:
            return False
        return any(cf in node.get("source_file", "") for cf in candidate_files)

    edge_count = {}
    for link in graph.get("links", []):
        edge_count[link.get("source")] = edge_count.get(link.get("source"), 0) + 1
        edge_count[link.get("target")] = edge_count.get(link.get("target"), 0) + 1

    requirement_text = " ".join(h["document"] for h in requirement_hits).lower()

    targets = []
    for node in nodes:
        if not node.get("_callable"):
            continue
        score = 0.0
        rationale = []
        if target_class:
            # Deterministic override: every callable in the target class is
            # eligible, structural fan-in only breaks ties between them.
            score += 100.0
            rationale.append(f"explicit --target-class={target_class}")
        if touches_changed_files(node):
            score += 10.0
            rationale.append("touches PR diff")
        label_terms = node.get("label", "").strip(".()").lower()
        if label_terms and label_terms in requirement_text:
            # Weighted much higher than structural fan-in (previously 5.0,
            # comparable to ~5 edges of fan-in) so a real RAG match reliably
            # outranks a high-fan-in "god node" that has nothing to do with
            # the actual question/spec being asked about.
            score += 50.0
            rationale.append("mentioned in retrieved requirement text")
        score += min(edge_count.get(node.get("id"), 0), 10) * 0.1
        if score <= 0:
            continue
        targets.append(
            {
                "node_id": node.get("id"),
                "label": node.get("label"),
                "source_file": node.get("source_file"),
                "score": round(score, 2),
                "rationale": "; ".join(rationale) or "structural fan-in",
            }
        )
    targets.sort(key=lambda t: t["score"], reverse=True)
    return targets


def plan_targets(payload: dict) -> dict:
    """Handler for the Planner agent's A2A skill.

    payload = {
        "mode": "spec" | "pr",
        "question": str,               # question to retrieve requirements for
        "changed_files": [str, ...],   # optional, PR mode (FR-14)
        "max_targets": int,            # optional
        "target_class": str | None,    # optional deterministic override
    }
    """
    question = payload.get("question", "")
    changed_files = payload.get("changed_files", [])
    max_targets = payload.get("max_targets", 5)
    target_class = payload.get("target_class")

    requirement_hits = query_requirements(question) if question else []
    ranked = _rank_targets(changed_files, requirement_hits, target_class=target_class)

    return {
        "targets": ranked[:max_targets],
        "requirement_context": [h["metadata"] for h in requirement_hits],
    }



agent_card = build_agent_card(
    name="TestPlannerAgent",
    description="Plans ranked test targets using Graphify structural context + RAG requirements.",
    url=AGENT_URL,
    skill_id="plan_test_targets",
    skill_description="Given a question/PR diff, returns ranked test targets with rationale.",
    tags=["qa", "planning"],
)
app = build_agent_app(agent_card, plan_targets)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8801)
