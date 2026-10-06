"""Structured version of demo_snapshot.py's checks, for the UI's header
status strip (AI-generated test count, coverage, report count, RAG/graph
presence) - reuses the same settings/paths, just returns JSON instead of
printing.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402


def _tracked_test_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "src/test/java"],
        cwd=str(settings.sut_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    return set(result.stdout.splitlines())


def get_snapshot() -> dict:
    tracked = _tracked_test_files()
    test_root = settings.sut_dir / "src" / "test" / "java"
    generated = []
    if test_root.exists():
        for java_file in sorted(test_root.rglob("*.java")):
            rel = java_file.relative_to(settings.sut_dir).as_posix()
            if rel not in tracked:
                generated.append(rel)

    jacoco_xml = settings.sut_dir / "target" / "site" / "jacoco" / "jacoco.xml"
    coverage = None
    if jacoco_xml.exists():
        from mcp_servers import maven_mcp_server as maven_tools

        report = maven_tools.get_coverage_report()
        coverage = {
            "line_pct": report.get("overall_line_pct", 0.0),
            "branch_pct": report.get("overall_branch_pct", 0.0),
        }

    qa_reports = sorted(settings.reports_dir.glob("qa_report_*.md"))
    suite_health_path = settings.reports_dir / "suite_health.json"
    run_count = 0
    if suite_health_path.exists():
        run_count = len(json.loads(suite_health_path.read_text(encoding="utf-8")).get("runs", []))

    rag_present = settings.chroma_dir.exists() and any(settings.chroma_dir.iterdir())

    graph_json = settings.graphify_out_dir / "graph.json"
    graph_info = None
    if graph_json.exists():
        data = json.loads(graph_json.read_text(encoding="utf-8"))
        graph_info = {
            "nodes": len(data.get("nodes", [])),
            "edges": len(data.get("links", [])),
            "has_report": (settings.graphify_out_dir / "GRAPH_REPORT.md").exists(),
            "has_html": (settings.graphify_out_dir / "graph.html").exists(),
        }

    return {
        "generated_test_files": generated,
        "coverage": coverage,
        "report_count": len(qa_reports),
        "run_count": run_count,
        "rag_present": rag_present,
        "graph": graph_info,
    }
