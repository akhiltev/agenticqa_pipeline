"""Converts Graphify's graph.json into React-Flow-shaped node/edge JSON,
attaches per-node JaCoCo coverage %, and provides a "god nodes + neighbors"
default scoped view plus an expand-on-click operation, so the UI never has
to render all ~1400 nodes at once.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_servers import graphify_mcp_server as graphify_tools  # noqa: E402
from mcp_servers import maven_mcp_server as maven_tools  # noqa: E402

DEFAULT_GOD_NODE_COUNT = 8
DEFAULT_NEIGHBOR_DEPTH = 1


def _class_coverage_map() -> dict[str, float]:
    """Maps simple class name (e.g. "CDL") -> line coverage % from the last
    JaCoCo report, if any."""
    report = maven_tools.get_coverage_report()
    if report.get("error"):
        return {}
    out = {}
    for cls in report.get("classes", []):
        simple_name = cls["class"].rsplit(".", 1)[-1].split("$")[0]
        # Keep the highest (outer-class) coverage figure if multiple inner
        # classes share a simple-name prefix collision; first-write wins.
        out.setdefault(simple_name, cls["line_pct"])
    return out


def _node_to_flow(node: dict, coverage_map: dict[str, float]) -> dict:
    label = node.get("label", "")
    simple_name = label.strip(".()").replace(".java", "")
    coverage = coverage_map.get(simple_name)
    return {
        "id": node["id"],
        "type": "default",
        "data": {
            "label": label,
            "file_type": node.get("file_type"),
            "source_file": node.get("source_file"),
            "callable": bool(node.get("_callable")),
            "coverage_pct": coverage,
        },
        "position": {"x": 0, "y": 0},  # frontend applies dagre layout
    }


def _edge_to_flow(link: dict, idx: int) -> dict:
    return {
        "id": f"e{idx}",
        "source": link.get("source"),
        "target": link.get("target"),
        "label": link.get("relation"),
        "data": {"confidence": link.get("confidence")},
        "animated": link.get("confidence") == "INFERRED",
    }


def get_default_view(
    god_node_count: int = DEFAULT_GOD_NODE_COUNT,
    depth: int = DEFAULT_NEIGHBOR_DEPTH,
) -> dict:
    """God nodes (highest degree) + their N-hop neighbors - a readable
    default subgraph instead of dumping all ~1400 nodes into React Flow.

    Restricted to src/main/java "class" nodes (the CLI's own
    `graphify god-nodes` reports whole-class nodes like JSONObjectTest at
    the top by raw degree, but those are test classes with many outgoing
    "calls" edges, not the interesting production abstractions to browse
    coverage against - main-source classes are what the Coverage tab and
    the demo's --target-class flow actually care about).
    """
    graph = graphify_tools._load_graph()
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    links = graph.get("links", [])

    degree: dict[str, int] = {}
    for link in links:
        degree[link.get("source")] = degree.get(link.get("source"), 0) + 1
        degree[link.get("target")] = degree.get(link.get("target"), 0) + 1

    def is_main_class(node: dict) -> bool:
        return (
            node.get("file_type") == "code"
            and "src/main/java" in node.get("source_file", "")
            and node.get("_callable_class")
        )

    god_ids = [
        node_id
        for node_id, _ in sorted(degree.items(), key=lambda kv: kv[1], reverse=True)
        if is_main_class(nodes_by_id.get(node_id, {}))
    ][:god_node_count]

    return expand_subgraph(god_ids, depth=depth)


def expand_subgraph(seed_ids: list[str], depth: int = 1) -> dict:
    """Returns seed_ids + their neighbors up to `depth` hops, converted to
    React Flow shape."""
    graph = graphify_tools._load_graph()
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    links = graph.get("links", [])

    frontier = set(seed_ids)
    visited = set(seed_ids)
    for _ in range(max(depth, 0)):
        next_frontier = set()
        for link in links:
            src, tgt = link.get("source"), link.get("target")
            if src in frontier and tgt not in visited:
                next_frontier.add(tgt)
            if tgt in frontier and src not in visited:
                next_frontier.add(src)
        visited |= next_frontier
        frontier = next_frontier

    coverage_map = _class_coverage_map()
    flow_nodes = [
        _node_to_flow(nodes_by_id[nid], coverage_map)
        for nid in visited
        if nid in nodes_by_id
    ]
    flow_edges = [
        _edge_to_flow(link, i)
        for i, link in enumerate(links)
        if link.get("source") in visited and link.get("target") in visited
    ]
    return {"nodes": flow_nodes, "edges": flow_edges}


def find_node_id_by_label(query: str) -> list[dict]:
    """Case-insensitive substring search over node labels, for the UI's
    search box (e.g. typing "StringBuilderWriter")."""
    graph = graphify_tools._load_graph()
    query_lower = query.lower()
    matches = []
    for node in graph.get("nodes", []):
        label = node.get("label", "")
        if query_lower in label.lower():
            matches.append({"id": node["id"], "label": label, "source_file": node.get("source_file")})
    return matches[:25]


def get_view_for_class(class_name: str, depth: int = 1) -> dict:
    """Subgraph scoped to a specific class by name (used by the Run tab's
    embedded preview, which only knows the --target-class string, not a
    node id) - matches the same class-membership rule the Planner agent's
    _rank_targets(target_class=...) override uses, so the graph shown here
    corresponds to exactly what the Planner will pick from.
    """
    graph = graphify_tools._load_graph()
    target_lower = class_name.lower()
    seed_ids = [
        n["id"]
        for n in graph.get("nodes", [])
        if target_lower in n.get("source_file", "").lower()
        or target_lower == n.get("label", "").strip(".()").lower()
    ]
    if not seed_ids:
        return {"nodes": [], "edges": []}
    return expand_subgraph(seed_ids, depth=depth)

