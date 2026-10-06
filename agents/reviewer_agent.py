"""Reviewer Agent (FR-20, FR-21, FR-22, FR-23): decides whether to continue
iterating, drafts the human-readable QA report, posts a PR-comment-style
summary in PR mode, and maintains the cross-run suite_health.json ledger.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.a2a_common import build_agent_app, build_agent_card  # noqa: E402
from config.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)

AGENT_URL = "http://127.0.0.1:8803/"


def _load_suite_health() -> dict:
    path = settings.reports_dir / "suite_health.json"
    if not path.exists():
        return {"runs": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_suite_health(data: dict) -> None:
    settings.ensure_dirs()
    path = settings.reports_dir / "suite_health.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def review(payload: dict) -> dict:
    """Handler for the Reviewer agent's A2A skill.

    payload = {
        "mode": "spec" | "pr",
        "pr_id": str | None,
        "coverage_before": {...},   # get_coverage_report() output
        "coverage_after": {...},
        "generated": [ {status, class_name, attempts, ...}, ... ],
        "iteration": int,
        "max_iterations": int,
    }
    """
    coverage_before = payload.get("coverage_before", {})
    coverage_after = payload.get("coverage_after", {})
    generated = payload.get("generated", [])
    iteration = payload.get("iteration", 1)
    max_iterations = payload.get("max_iterations", settings.max_plan_generate_iterations)
    post_generation_build_success = payload.get("post_generation_build_success", True)

    before_line = coverage_before.get("overall_line_pct", 0.0)
    after_line = coverage_after.get("overall_line_pct", 0.0)
    delta = round(after_line - before_line, 2)

    # If the post-generation build failed, coverage_after is stale (it comes
    # from the last successful jacoco.xml, not this run) - do not let a
    # false "target_met" mask a build that a generated test correctly broke
    # by exposing a real bug in the SUT (this happened during validation:
    # CDL.toJSONArray genuinely does not skip trailing blank lines yet).
    target_met = post_generation_build_success and after_line >= settings.coverage_target_pct
    budget_exhausted = iteration >= max_iterations
    should_continue = (
        post_generation_build_success and not target_met and not budget_exhausted
    )

    accepted = [g for g in generated if g.get("status") == "accepted"]
    rejected = [g for g in generated if g.get("status") != "accepted"]

    report_md = _render_report(
        payload, coverage_before, coverage_after, delta, accepted, rejected,
        post_generation_build_success,
    )
    report_path = _save_report(report_md)
    _update_suite_health(payload.get("mode", "spec"), payload.get("pr_id"), coverage_after)

    pr_comment = None
    if payload.get("mode") == "pr":
        pr_comment = _render_pr_comment(coverage_before, coverage_after, delta, accepted, rejected)

    return {
        "should_continue": should_continue,
        "target_met": target_met,
        "budget_exhausted": budget_exhausted,
        "post_generation_build_success": post_generation_build_success,
        "coverage_delta_line_pct": delta,
        "report_path": str(report_path),
        "pr_comment": pr_comment,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
    }


def _render_report(payload, before, after, delta, accepted, rejected, build_success=True) -> str:
    lines = [
        "# QA Report",
        "",
        f"- Mode: `{payload.get('mode', 'spec')}`",
        f"- PR: `{payload.get('pr_id')}`" if payload.get("pr_id") else "",
        f"- Iteration: {payload.get('iteration', 1)} / {payload.get('max_iterations', settings.max_plan_generate_iterations)}",
        "",
    ]
    if not build_success:
        lines += [
            "## \u26a0\ufe0f Build Failed After Generation",
            "",
            "`mvn test` failed after writing the generated test(s) below. This "
            "commonly means a generated test correctly exposes a real, "
            "pre-existing defect in the system under test (the assertions "
            "are valid Java and compiled, but failed at runtime). Coverage "
            "numbers below reflect the last **successful** build, not this "
            "failed run. See `sut/target/surefire-reports/` for failure "
            "details.",
            "",
        ]
    lines += [
        "## Coverage",
        f"- Line coverage before: {before.get('overall_line_pct', 0.0)}%",
        f"- Line coverage after: {after.get('overall_line_pct', 0.0)}%",
        f"- Delta: {delta:+.2f} pts",
        f"- Branch coverage after: {after.get('overall_branch_pct', 0.0)}%",
        "",
        f"## Tests Generated ({len(accepted)} accepted, {len(rejected)} rejected)",
    ]
    for g in accepted:
        lines.append(f"- ACCEPTED `{g.get('class_name')}` (attempts: {g.get('attempts')})")
    for g in rejected:
        status_label = g.get("status", "rejected").upper()
        lines.append(
            f"- {status_label} (`{g.get('class_name', target_label(g))}`) "
            f"after {g.get('attempts', '?')} attempt(s): {g.get('errors')}"
        )
    return "\n".join(line for line in lines if line is not None)


def target_label(g: dict) -> str:
    return g.get("class_name") or "?"


def _render_pr_comment(before, after, delta, accepted, rejected) -> str:
    return (
        f"**AI QA Engineer Summary**\n\n"
        f"Line coverage: {before.get('overall_line_pct', 0.0)}% -> "
        f"{after.get('overall_line_pct', 0.0)}% ({delta:+.2f} pts)\n"
        f"Tests generated: {len(accepted)} accepted, {len(rejected)} rejected.\n"
    )


def _save_report(report_md: str) -> Path:
    settings.ensure_dirs()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = settings.reports_dir / f"qa_report_{timestamp}.md"
    path.write_text(report_md, encoding="utf-8")
    return path


def _update_suite_health(mode: str, pr_id, coverage_after: dict) -> None:
    data = _load_suite_health()
    data["runs"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "pr_id": pr_id,
            "overall_line_pct": coverage_after.get("overall_line_pct", 0.0),
            "overall_branch_pct": coverage_after.get("overall_branch_pct", 0.0),
            "per_class": {
                c["class"]: c["line_pct"] for c in coverage_after.get("classes", [])
            },
        }
    )
    _save_suite_health(data)


agent_card = build_agent_card(
    name="ReviewerAgent",
    description="Reviews coverage deltas, decides on iteration, writes QA report.",
    url=AGENT_URL,
    skill_id="review_run",
    skill_description="Given coverage before/after + generated tests, produces a QA verdict/report.",
    tags=["qa", "review", "reporting"],
)
app = build_agent_app(agent_card, review)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8803)
