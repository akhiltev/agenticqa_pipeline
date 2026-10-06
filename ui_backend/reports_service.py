"""Lists and reads QA reports (reports/qa_report_*.md) for the UI's Reports
tab.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402


def list_reports() -> list[dict]:
    reports = sorted(
        settings.reports_dir.glob("qa_report_*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [
        {"name": p.name, "modified": p.stat().st_mtime}
        for p in reports
    ]


def get_report(name: str) -> str | None:
    # Guard against path traversal - only allow the exact expected filename shape.
    if not name.startswith("qa_report_") or not name.endswith(".md") or "/" in name or "\\" in name:
        return None
    path = settings.reports_dir / name
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
