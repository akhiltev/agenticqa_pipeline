"""Demo state snapshot: prints a concise summary of the repo's current
"AI QA Engineer" state - useful to run before and after run_demo.py so you
can narrate the before/after story clearly while demoing.

Usage:
    .venv\\Scripts\\python.exe demo_snapshot.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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


def print_generated_tests() -> None:
    print("=== AI-generated test files currently in the SUT ===")
    tracked = _tracked_test_files()
    test_root = settings.sut_dir / "src" / "test" / "java"
    if not test_root.exists():
        print("  (sut/src/test/java not found)")
        return
    generated = []
    for java_file in sorted(test_root.rglob("*.java")):
        rel = java_file.relative_to(settings.sut_dir).as_posix()
        if rel not in tracked:
            generated.append(rel)
    if not generated:
        print("  none (clean baseline - no AI-generated tests present)")
    else:
        for rel in generated:
            print(f"  + {rel}")
        print(f"  ({len(generated)} AI-generated test file(s) total)")


def print_coverage() -> None:
    print("\n=== Current JaCoCo coverage (last build, if any) ===")
    jacoco_xml = settings.sut_dir / "target" / "site" / "jacoco" / "jacoco.xml"
    if not jacoco_xml.exists():
        print("  no jacoco.xml found yet - run mvn test (or run_demo.py) first.")
        return
    from mcp_servers import maven_mcp_server as maven_tools

    report = maven_tools.get_coverage_report()
    print(f"  Line coverage:   {report.get('overall_line_pct', 0.0):.2f}%")
    print(f"  Branch coverage: {report.get('overall_branch_pct', 0.0):.2f}%")


def print_reports() -> None:
    print("\n=== QA reports (reports/) ===")
    qa_reports = sorted(settings.reports_dir.glob("qa_report_*.md"))
    if not qa_reports:
        print("  none yet")
    else:
        for p in qa_reports:
            print(f"  {p.name}")
        print(f"  ({len(qa_reports)} report(s) total)")

    suite_health = settings.reports_dir / "suite_health.json"
    if suite_health.exists():
        import json

        data = json.loads(suite_health.read_text(encoding="utf-8"))
        runs = data.get("runs", [])
        print(f"\n  suite_health.json: {len(runs)} run(s) recorded")
        if runs:
            last = runs[-1]
            print(
                f"  last run: {last.get('timestamp')} mode={last.get('mode')} "
                f"line={last.get('overall_line_pct')}% branch={last.get('overall_branch_pct')}%"
            )
    else:
        print("\n  suite_health.json: not present")


def print_rag_state() -> None:
    print("\n=== RAG vector store ===")
    if settings.chroma_dir.exists() and any(settings.chroma_dir.iterdir()):
        print(f"  present at {settings.chroma_dir}")
    else:
        print("  empty/not present (will be built on next run_demo.py run)")


def print_graph_state() -> None:
    print("\n=== Graphify knowledge graph ===")
    graph_json = settings.graphify_out_dir / "graph.json"
    if graph_json.exists():
        import json

        data = json.loads(graph_json.read_text(encoding="utf-8"))
        print(
            f"  present: {len(data.get('nodes', []))} nodes, "
            f"{len(data.get('links', []))} edges"
        )
        report_md = settings.graphify_out_dir / "GRAPH_REPORT.md"
        html = settings.graphify_out_dir / "graph.html"
        print(f"  GRAPH_REPORT.md: {'present' if report_md.exists() else 'not generated (run graphify cluster-only)'}")
        print(f"  graph.html:      {'present' if html.exists() else 'not generated (run graphify cluster-only)'}")
    else:
        print("  not present (will be built on next run_demo.py run)")


def main() -> None:
    print("############################################")
    print("# Agentic QA Pipeline - Demo State Snapshot #")
    print("############################################\n")
    print_generated_tests()
    print_coverage()
    print_reports()
    print_rag_state()
    print_graph_state()
    print()


if __name__ == "__main__":
    main()
