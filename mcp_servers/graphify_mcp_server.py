"""MCP server exposing Graphify knowledge-graph queries as tools (FR-1, FR-2).

Wraps `graphify update` (deterministic AST extraction, no LLM required - see
REQUIREMENTS.md section 10) plus direct reads of the resulting `graph.json`
so agents can query structural context without shelling out themselves.

Run standalone (stdio transport) for real MCP clients:
    python mcp_servers/graphify_mcp_server.py
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)

server = MCPServer(name="graphify-mcp", version="0.1.0")

GRAPHIFY_EXE = settings.project_root / ".venv" / "Scripts" / "graphify.exe"


def _graph_path() -> Path:
    return settings.graphify_out_dir / "graph.json"


def _load_graph() -> dict:
    path = _graph_path()
    if not path.exists():
        return {"nodes": [], "links": [], "directed": False}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@server.tool()
def rebuild_graph() -> dict:
    """Runs `graphify update` (AST-only, no LLM) to (re)build the knowledge
    graph for the whole SUT (FR-1). Always targets the SUT root so
    graph.json consistently lands at settings.graphify_out_dir; PR-mode
    scoping (FR-3, FR-14) is done via find_nodes_for_file()/get_neighbors()
    queries against the resulting graph rather than by limiting the
    extraction directory (graphify writes graphify-out/ next to whatever
    directory it is pointed at, which would otherwise fragment the graph
    location).
    """
    proc = subprocess.run(
        [str(GRAPHIFY_EXE), "update", str(settings.sut_dir), "--no-cluster"],
        cwd=str(settings.sut_dir),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-2000:],
        "graph_path": str(_graph_path()),
    }


@server.tool()
def cluster_only() -> dict:
    """Runs `graphify cluster-only .` against the SUT: re-clusters the
    existing graph.json and regenerates GRAPH_REPORT.md + graph.html (the
    human-readable report + interactive graph, per the CLI workflow
    documented in README.md). Slower than rebuild_graph() (community
    detection + optional LLM labeling), so this is a separate, explicit
    action rather than something run_demo.py does automatically.
    """
    proc = subprocess.run(
        [str(GRAPHIFY_EXE), "cluster-only", "."],
        cwd=str(settings.sut_dir),
        capture_output=True,
        text=True,
        timeout=600,
    )
    report_path = settings.graphify_out_dir / "GRAPH_REPORT.md"
    html_path = settings.graphify_out_dir / "graph.html"
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-2000:],
        "report_path": str(report_path),
        "html_path": str(html_path),
        "has_report": report_path.exists(),
        "has_html": html_path.exists(),
    }


def _run_query_command(args: list[str]) -> dict:
    """Shared runner for the read-only `graphify <cmd> ... --graph
    graph.json` CLI queries (god-nodes/explain/path/affected/query),
    exactly mirroring what a user would type at the terminal.
    """
    graph_path = _graph_path()
    proc = subprocess.run(
        [str(GRAPHIFY_EXE), *args, "--graph", str(graph_path)],
        cwd=str(settings.project_root),
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


@server.tool()
def god_nodes(top: int = 10) -> dict:
    """`graphify god-nodes --graph graph.json --top N`"""
    return _run_query_command(["god-nodes", "--top", str(top)])


@server.tool()
def explain_node(name: str) -> dict:
    """`graphify explain "<name>" --graph graph.json`"""
    return _run_query_command(["explain", name])


@server.tool()
def path_between(a: str, b: str) -> dict:
    """`graphify path "<a>" "<b>" --graph graph.json`"""
    return _run_query_command(["path", a, b])


@server.tool()
def affected_by(name: str) -> dict:
    """`graphify affected "<name>" --graph graph.json`"""
    return _run_query_command(["affected", name])


@server.tool()
def query_graph(question: str) -> dict:
    """`graphify query "<question>" --graph graph.json` (BFS traversal,
    not an LLM call - deterministic, no API key needed).
    """
    return _run_query_command(["query", question])





@server.tool()
def list_nodes(file_type: str = "") -> list[dict]:
    """Lists nodes in the current knowledge graph, optionally filtered by
    file_type (e.g. "code") (FR-2).
    """
    graph = _load_graph()
    nodes = graph.get("nodes", [])
    if file_type:
        nodes = [n for n in nodes if n.get("file_type") == file_type]
    return nodes


@server.tool()
def list_known_labels() -> list[str]:
    """Returns the set of all node labels (class/method names) known to the
    graph - used by the Generator's hallucination guardrail (FR-16).
    """
    graph = _load_graph()
    labels = set()
    for n in graph.get("nodes", []):
        label = n.get("label", "")
        cleaned = label.replace(".java", "").lstrip(".").rstrip("()")
        if cleaned:
            labels.add(cleaned)
    return sorted(labels)


@server.tool()
def get_neighbors(node_id: str) -> list[dict]:
    """Returns all edges (links) touching the given node id (FR-2)."""
    graph = _load_graph()
    return [
        link
        for link in graph.get("links", [])
        if link.get("source") == node_id or link.get("target") == node_id
    ]


@server.tool()
def get_class_methods() -> dict[str, list[str]]:
    """Returns {ClassName: [methodName, ...]} derived from the graph's
    "method" relation edges (class node -> method node) (FR-2). Used by the
    Generator's hallucination guardrail to catch calls like
    `JSONArray.toJSONArray(...)` where `toJSONArray` is a real method name
    in the codebase but not actually defined on `JSONArray` (a real gap
    found during validation: a flat label-only check let this hallucinated
    call slip through and fail to compile).
    """
    graph = _load_graph()
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    result: dict[str, set[str]] = {}
    for link in graph.get("links", []):
        if link.get("relation") != "method":
            continue
        class_node = nodes_by_id.get(link.get("source"))
        method_node = nodes_by_id.get(link.get("target"))
        if not class_node or not method_node:
            continue
        class_name = class_node.get("label", "").replace(".java", "")
        method_name = method_node.get("label", "").strip(".()")
        if class_name and method_name:
            result.setdefault(class_name, set()).add(method_name)
    return {k: sorted(v) for k, v in result.items()}


@server.tool()
def find_nodes_for_file(source_file: str) -> list[dict]:
    """Returns all nodes extracted from a given source file path - used to
    scope test-target discovery to a PR's changed files (FR-3, FR-14).
    """
    graph = _load_graph()
    return [n for n in graph.get("nodes", []) if source_file in n.get("source_file", "")]


if __name__ == "__main__":
    server.run(transport="stdio")
