"""Demo-day reset: restores the repo to a clean, pristine "before" state so
you can show a real before/after story when demoing the AI QA Engineer
pipeline (run_demo.py).

Resets:
  - reports/*.md and reports/suite_health.json (fresh report history)
  - rag/chroma_store/ (fresh RAG index - required after any embedding
    backend change anyway, see REQUIREMENTS.md 6a)
  - sut/graphify-out/ (fresh knowledge graph; run_demo.py rebuilds it
    automatically on the next run, or you can rebuild it live for the demo)
  - sut/target/ (fresh Maven build output)
  - sut/src/test/java/.../*.java: any AI-generated test file not tracked in
    git is removed; `git checkout -- .` restores any tracked file that a
    prior run may have edited (should never happen given write_test_file's
    collision protection, but this is a safety net)

Usage:
    .venv\\Scripts\\python.exe reset_demo_state.py                # reset only
    .venv\\Scripts\\python.exe reset_demo_state.py --baseline-build
        # also rebuilds a clean baseline (mvn test + JaCoCo) so you have a
        # "before" coverage report ready to show, with zero AI-generated
        # tests in it yet.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings  # noqa: E402


def _rm(path: Path, label: str) -> None:
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        print(f"  removed: {label} ({path})")
    else:
        print(f"  (already clean) {label}")


def reset_reports() -> None:
    print("=== Resetting reports/ ===")
    for md in sorted(settings.reports_dir.glob("qa_report_*.md")):
        _rm(md, "qa report")
    _rm(settings.reports_dir / "suite_health.json", "suite_health.json")


def reset_rag() -> None:
    print("=== Resetting RAG vector store ===")
    _rm(settings.chroma_dir, "chroma_store")


def reset_graphify() -> None:
    print("=== Resetting Graphify knowledge graph ===")
    _rm(settings.graphify_out_dir, "graphify-out")


def reset_maven_build() -> None:
    print("=== Resetting Maven build output ===")
    _rm(settings.sut_dir / "target", "sut/target")


def restore_sut_git_state() -> None:
    print("=== Restoring SUT to pristine git state (test sources only) ===")
    # IMPORTANT: only restore src/test/java, never `git checkout -- .` on the
    # whole repo - sut/pom.xml has an intentional, permanent JaCoCo plugin
    # addition (see REQUIREMENTS.md section 10) that must NOT be reverted.
    subprocess.run(
        ["git", "checkout", "--", "src/test/java"],
        cwd=str(settings.sut_dir),
        check=False,
    )

    pom = (settings.sut_dir / "pom.xml").read_text(encoding="utf-8")
    if "jacoco-maven-plugin" not in pom:
        print(
            "  WARNING: jacoco-maven-plugin is missing from sut/pom.xml! "
            "JaCoCo reports will not be generated. See REQUIREMENTS.md "
            "section 10 to re-add it, or re-clone sut/ and re-apply the "
            "JaCoCo plugin addition."
        )
    else:
        print("  pom.xml JaCoCo plugin: present (untouched)")

    tracked = set(
        subprocess.run(
            ["git", "ls-files", "src/test/java"],
            cwd=str(settings.sut_dir),
            capture_output=True,
            text=True,
            check=False,
        ).stdout.splitlines()
    )
    test_root = settings.sut_dir / "src" / "test" / "java"
    removed = 0
    for java_file in test_root.rglob("*.java"):
        rel = java_file.relative_to(settings.sut_dir).as_posix()
        if rel not in tracked:
            java_file.unlink()
            removed += 1
            print(f"  removed AI-generated test file: {rel}")
    if removed == 0:
        print("  (no untracked test files found - already clean)")
    else:
        print(f"  removed {removed} untracked test file(s).")


def run_baseline_build() -> None:
    print("=== Running clean baseline build (mvn test + JaCoCo) ===")
    from mcp_servers import maven_mcp_server as maven_tools

    result = maven_tools.run_tests()
    if result.get("build_success"):
        report = maven_tools.get_coverage_report()
        print(
            f"  BUILD SUCCESS - baseline coverage: "
            f"line={report.get('overall_line_pct', 0.0):.2f}% "
            f"branch={report.get('overall_branch_pct', 0.0):.2f}%"
        )
    else:
        print("  WARNING: baseline build did not succeed. Last 40 lines of output:")
        print("\n".join(result.get("stdout", "").splitlines()[-40:]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-build",
        action="store_true",
        help="Also run a clean mvn test after resetting, so a 'before' "
        "JaCoCo report is ready to show immediately.",
    )
    parser.add_argument(
        "--keep-reports",
        action="store_true",
        help="Skip clearing reports/ (useful if you want to keep history "
        "across a rehearsal run).",
    )
    args = parser.parse_args()

    print("Resetting demo state to a clean 'before' snapshot...\n")

    if not args.keep_reports:
        reset_reports()
    reset_rag()
    reset_graphify()
    reset_maven_build()
    restore_sut_git_state()

    if args.baseline_build:
        run_baseline_build()

    print("\nDone. Repo is now in a clean 'before' state for your demo.")
    print("Run: .\\.venv\\Scripts\\python.exe demo_snapshot.py   to see a summary.")


if __name__ == "__main__":
    main()
