"""Thin wrappers around maven_mcp_server + reports/suite_health.json for the
UI's Coverage tab (current coverage, per-class breakdown, run history).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402
from mcp_servers import maven_mcp_server as maven_tools  # noqa: E402


def get_current_coverage() -> dict:
    return maven_tools.get_coverage_report()


def get_jacoco_report_info() -> dict:
    """Whether the real JaCoCo HTML report (sut/target/site/jacoco/index.html)
    exists, plus the URL the UI can open it at (served statically by
    ui_backend.api). Kept separate from get_current_coverage() since the
    XML-derived summary can exist independently of/before the full HTML site
    is regenerated (both come from the same `mvn test` run in practice).
    """
    index = settings.sut_dir / "target" / "site" / "jacoco" / "index.html"
    return {"exists": index.exists(), "url": "/api/jacoco/html/index.html" if index.exists() else None}


def class_report_url(class_name: str) -> str | None:
    """Maps a fully-qualified class name (e.g. 'org.json.CDL') to its
    per-class JaCoCo HTML report URL (e.g. 'org.json/CDL.html'), which shows
    green/red line-by-line source highlighting - much more actionable than
    the flat percentage table for figuring out exactly what to cover next.
    """
    index = settings.sut_dir / "target" / "site" / "jacoco" / "index.html"
    if not index.exists():
        return None
    if "." not in class_name:
        return None
    package, _, simple = class_name.rpartition(".")
    html_path = settings.sut_dir / "target" / "site" / "jacoco" / package / f"{simple}.html"
    if not html_path.exists():
        return None
    return f"/api/jacoco/html/{package}/{simple}.html"


def get_run_history() -> list[dict]:
    path = settings.reports_dir / "suite_health.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("runs", [])


def get_latest_delta() -> dict | None:
    runs = get_run_history()
    if len(runs) < 2:
        return None
    prev, curr = runs[-2], runs[-1]
    prev_line = prev.get("overall_line_pct", 0.0)
    curr_line = curr.get("overall_line_pct", 0.0)
    prev_classes = prev.get("per_class", {})
    curr_classes = curr.get("per_class", {})
    changed = []
    for cls in sorted(set(prev_classes) | set(curr_classes)):
        before = prev_classes.get(cls)
        after = curr_classes.get(cls)
        if before is not None and after is not None and round(after - before, 2) != 0:
            changed.append({"class": cls, "before": before, "after": after, "delta": round(after - before, 2)})
    return {
        "prev_timestamp": prev.get("timestamp"),
        "curr_timestamp": curr.get("timestamp"),
        "overall_line_delta": round(curr_line - prev_line, 2),
        "overall_branch_delta": round(
            curr.get("overall_branch_pct", 0.0) - prev.get("overall_branch_pct", 0.0), 2
        ),
        "per_class_changes": sorted(changed, key=lambda c: -abs(c["delta"])),
    }
