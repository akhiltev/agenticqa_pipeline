"""Coverage delta viewer: compares the last two runs recorded in
reports/suite_health.json and prints per-class movement, plus overall
line/branch deltas. Useful for seeing whether the AI QA Engineer pipeline
is actually improving the suite run-over-run (REQUIREMENTS.md FR-23).

Usage:
    .venv\\Scripts\\python.exe view_coverage_deltas.py            # last 2 runs
    .venv\\Scripts\\python.exe view_coverage_deltas.py --all      # full history
    .venv\\Scripts\\python.exe view_coverage_deltas.py --n 3      # last 3 runs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings  # noqa: E402


def load_runs() -> list[dict]:
    path = settings.reports_dir / "suite_health.json"
    if not path.exists():
        print(f"No suite_health.json found at {path}. Run run_demo.py at least once.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("runs", [])


def print_run_summary(runs: list[dict]) -> None:
    print("=== Run history (overall coverage) ===")
    header = f"{'#':>3}  {'timestamp':<26} {'mode':<6} {'pr_id':<10} {'line%':>7} {'branch%':>8}"
    print(header)
    print("-" * len(header))
    for i, run in enumerate(runs):
        print(
            f"{i:>3}  {run.get('timestamp', ''):<26} {run.get('mode', ''):<6} "
            f"{str(run.get('pr_id') or '-'):<10} "
            f"{run.get('overall_line_pct', 0.0):>6.2f}% {run.get('overall_branch_pct', 0.0):>7.2f}%"
        )
    print()


def print_delta(prev: dict, curr: dict) -> None:
    prev_line = prev.get("overall_line_pct", 0.0)
    curr_line = curr.get("overall_line_pct", 0.0)
    prev_branch = prev.get("overall_branch_pct", 0.0)
    curr_branch = curr.get("overall_branch_pct", 0.0)

    print(
        f"=== Delta: run '{prev.get('timestamp')}' -> '{curr.get('timestamp')}' "
        f"({prev.get('mode')} -> {curr.get('mode')}) ==="
    )
    print(f"Overall line coverage:   {prev_line:6.2f}% -> {curr_line:6.2f}%  ({curr_line - prev_line:+.2f} pts)")
    print(f"Overall branch coverage: {prev_branch:6.2f}% -> {curr_branch:6.2f}%  ({curr_branch - prev_branch:+.2f} pts)")
    print()

    prev_classes = prev.get("per_class", {})
    curr_classes = curr.get("per_class", {})
    all_classes = sorted(set(prev_classes) | set(curr_classes))

    changed = []
    added = []
    removed = []
    for cls in all_classes:
        if cls not in prev_classes:
            added.append(cls)
            continue
        if cls not in curr_classes:
            removed.append(cls)
            continue
        delta = round(curr_classes[cls] - prev_classes[cls], 2)
        if delta != 0:
            changed.append((cls, prev_classes[cls], curr_classes[cls], delta))

    if changed:
        print(f"Per-class changes ({len(changed)}):")
        for cls, before, after, delta in sorted(changed, key=lambda t: -abs(t[3])):
            arrow = "\u2191" if delta > 0 else "\u2193"
            print(f"  {arrow} {cls:<45} {before:6.2f}% -> {after:6.2f}%  ({delta:+.2f} pts)")
    else:
        print("Per-class changes: none (coverage identical for all classes).")

    if added:
        print(f"\nNew classes in report ({len(added)}): {', '.join(added)}")
    if removed:
        print(f"\nClasses no longer in report ({len(removed)}): {', '.join(removed)}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="View JaCoCo coverage deltas across pipeline runs.")
    parser.add_argument("--n", type=int, default=2, help="Show the last N runs (default 2).")
    parser.add_argument("--all", action="store_true", help="Show full run history summary.")
    args = parser.parse_args()

    runs = load_runs()
    if not runs:
        print("No runs recorded yet.")
        return

    if args.all:
        print_run_summary(runs)
        return

    n = max(2, args.n)
    recent = runs[-n:]
    print_run_summary(recent)

    if len(recent) < 2:
        print("Need at least 2 runs to compute a delta. Run run_demo.py again.")
        return

    print_delta(recent[-2], recent[-1])


if __name__ == "__main__":
    main()
