"""Orchestrator (FR-24, FR-25, FR-26): single entrypoint that drives the
full AI QA Engineer pipeline end-to-end, in spec / pr / continuous mode.

Talks to the Planner/Generator/Reviewer agents over real A2A (JSON-RPC over
HTTP, per agents/a2a_common.py), and to Graphify/Maven via the MCP tool
functions directly in-process (mcp_servers/*.py remain independently
runnable as real stdio MCP servers for external MCP clients; the
orchestrator calls the underlying functions directly for reliability and to
avoid spawning extra subprocess layers in this demo).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402

from agents import generator_agent, planner_agent, reviewer_agent  # noqa: E402
from agents.a2a_client import call_agent  # noqa: E402
from config.settings import settings  # noqa: E402
from connectors.prs.factory import get_pr_connector  # noqa: E402
from connectors.requirements.factory import get_requirements_connector  # noqa: E402
from mcp_servers import graphify_mcp_server as graphify_tools  # noqa: E402
from mcp_servers import maven_mcp_server as maven_tools  # noqa: E402
from rag.index_specs import index_requirement_items, index_spec_files  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("orchestrator")

AGENTS = [
    (planner_agent.app, 8801, "Planner"),
    (generator_agent.app, 8802, "Generator"),
    (reviewer_agent.app, 8803, "Reviewer"),
]

ProgressCallback = Callable[[dict[str, Any]], None]


def _emit(progress_cb: ProgressCallback | None, event_type: str, **data: Any) -> None:
    """Pushes a structured progress event (used by ui_backend's SSE stream)
    in addition to the existing logger.info/warning calls, which remain the
    CLI's only output (this is purely additive - CLI behavior unchanged).
    """
    if progress_cb is not None:
        try:
            progress_cb({"type": event_type, **data})
        except Exception:  # noqa: BLE001
            logger.exception("progress_cb raised for event %s", event_type)


_AGENTS_STARTED = False


def _start_agent_servers() -> None:
    global _AGENTS_STARTED
    if _AGENTS_STARTED:
        return
    for app, port, name in AGENTS:
        def _run(app=app, port=port):
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        logger.info("Started %s agent on port %d", name, port)
    time.sleep(2.0)
    _AGENTS_STARTED = True



async def _run_pipeline(
    mode: str,
    pr_id: str | None,
    question: str,
    target_class: str | None = None,
    progress_cb: ProgressCallback | None = None,
) -> dict:
    _emit(progress_cb, "setup_graph_start")
    logger.info("=== Setup: (re)building Graphify knowledge graph ===")
    graph_result = await asyncio.to_thread(graphify_tools.rebuild_graph)
    logger.info("Graphify: %s", graph_result.get("stdout", "").strip().splitlines()[-1:])
    _emit(progress_cb, "setup_graph_done", stdout_tail=graph_result.get("stdout", "")[-500:])

    _emit(progress_cb, "setup_rag_start")
    logger.info("=== Setup: indexing requirements into RAG (Chroma) ===")
    req_connector = get_requirements_connector()
    items = await asyncio.to_thread(req_connector.fetch_items)
    n_indexed = await asyncio.to_thread(index_requirement_items, items)
    n_specs = await asyncio.to_thread(index_spec_files)
    logger.info("Indexed %d requirement items + %d spec files.", n_indexed, n_specs)
    _emit(progress_cb, "setup_rag_done", n_indexed=n_indexed, n_specs=n_specs)


    changed_files: list[str] = []
    linked_question = question
    if mode == "pr":
        pr_connector = get_pr_connector()
        pr = await asyncio.to_thread(pr_connector.fetch_pr, pr_id)
        if pr is None:
            raise SystemExit(f"PR {pr_id!r} not found via {settings.pr_source} connector.")
        changed_files = pr.changed_file_paths()
        linked_titles = []
        for wi_id in pr.linked_work_item_ids:
            item = await asyncio.to_thread(req_connector.fetch_item, wi_id)
            if item:
                linked_titles.append(item.title)
        linked_question = question or " ".join(linked_titles) or pr.title
        logger.info("PR %s: changed files=%s, linked work items=%s", pr.id, changed_files, pr.linked_work_item_ids)
        _emit(progress_cb, "pr_loaded", pr_id=pr.id, changed_files=changed_files)


    _emit(progress_cb, "baseline_build_start")
    logger.info("=== Baseline: running mvn test + JaCoCo ===")

    baseline_run = await asyncio.to_thread(maven_tools.run_tests)
    coverage_before = await asyncio.to_thread(maven_tools.get_coverage_report)

    logger.info(
        "Baseline coverage: line=%.2f%% branch=%.2f%% (build_success=%s)",
        coverage_before.get("overall_line_pct", 0.0),
        coverage_before.get("overall_branch_pct", 0.0),
        baseline_run.get("build_success"),
    )
    _emit(
        progress_cb,
        "baseline_build_done",
        build_success=baseline_run.get("build_success"),
        coverage=coverage_before,
    )

    generated_all: list[dict] = []
    coverage_after = coverage_before
    iteration = 0
    max_iterations = settings.max_plan_generate_iterations

    while True:
        iteration += 1
        _emit(progress_cb, "iteration_start", iteration=iteration, max_iterations=max_iterations)
        logger.info("=== Iteration %d/%d: Planner ===", iteration, max_iterations)
        plan_result = await call_agent(
            planner_agent.AGENT_URL,
            {
                "mode": mode,
                "question": linked_question,
                "changed_files": changed_files,
                "max_targets": 3,
                "target_class": target_class,
            },
        )
        targets = plan_result.get("targets", [])
        logger.info("Planner proposed %d target(s): %s", len(targets), [t.get("label") for t in targets])
        _emit(progress_cb, "planner_done", targets=targets)

        if not targets:
            logger.info("No targets proposed; stopping iteration loop.")
            _emit(progress_cb, "no_targets")
            break

        for target in targets:
            _emit(progress_cb, "generator_start", target=target)
            logger.info("=== Generator: %s ===", target.get("label"))
            gen_result = await call_agent(
                generator_agent.AGENT_URL,
                {
                    "target": target,
                    "rationale_context": linked_question,
                    "max_retries": settings.max_guardrail_retries,
                },
            )
            generated_all.append(gen_result)
            if gen_result.get("status") == "accepted":
                write_result = await asyncio.to_thread(
                    maven_tools.write_test_file, gen_result["relative_path"], gen_result["code"]
                )
                if write_result.get("collision"):
                    logger.warning(
                        "Test %s collided with an existing file; NOT written: %s",
                        gen_result.get("class_name"),
                        write_result.get("error"),
                    )
                    gen_result["status"] = "collision"
                    gen_result["errors"] = [write_result.get("error")]
                    _emit(progress_cb, "generator_result", target=target, result=gen_result)
                else:
                    logger.info(
                        "Wrote test %s; dry-compiling before accepting...",
                        gen_result.get("class_name"),
                    )
                    _emit(progress_cb, "compile_check_start", target=target, result=gen_result)
                    compile_result = await asyncio.to_thread(
                        maven_tools.check_compiles, gen_result["relative_path"]
                    )

                    if not compile_result.get("compiles"):
                        logger.warning(
                            "Generated test %s does NOT compile (a hallucination "
                            "Guardrails AI's regex checks missed - e.g. a wrong "
                            "constructor/method signature on a real class); "
                            "removing it. Errors: %s",
                            gen_result.get("class_name"),
                            compile_result.get("errors"),
                        )
                        written_path = Path(write_result["path"])
                        written_path.unlink(missing_ok=True)
                        gen_result["status"] = "compile_failed"
                        gen_result["errors"] = compile_result.get("errors")
                    else:
                        logger.info(
                            "Accepted test %s; compiles cleanly.",
                            gen_result.get("class_name"),
                        )
                    _emit(progress_cb, "generator_result", target=target, result=gen_result)
            else:
                logger.warning(
                    "Rejected target %s after %s attempt(s): %s",
                    target.get("label"),
                    gen_result.get("attempts", "?"),
                    gen_result.get("errors") or gen_result.get("raw") or gen_result,
                )
                _emit(progress_cb, "generator_result", target=target, result=gen_result)

        _emit(progress_cb, "post_generation_build_start")
        logger.info("=== Re-running mvn test + JaCoCo after generation ===")
        post_gen_run = await asyncio.to_thread(maven_tools.run_tests)

        if not post_gen_run.get("build_success"):
            logger.error(
                "mvn test FAILED after writing generated tests (this can mean "
                "a generated test correctly exposes a real, pre-existing bug "
                "in the SUT - see sut/target/surefire-reports for details). "
                "Coverage-after numbers below reflect the last SUCCESSFUL "
                "build, not this failed one."
            )
        coverage_after = await asyncio.to_thread(maven_tools.get_coverage_report)
        logger.info(
            "Coverage now: line=%.2f%% branch=%.2f%%",
            coverage_after.get("overall_line_pct", 0.0),
            coverage_after.get("overall_branch_pct", 0.0),
        )
        _emit(
            progress_cb,
            "post_generation_build_done",
            build_success=post_gen_run.get("build_success"),
            coverage=coverage_after,
        )

        _emit(progress_cb, "reviewer_start")
        logger.info("=== Reviewer ===")
        review_result = await call_agent(
            reviewer_agent.AGENT_URL,
            {
                "mode": mode,
                "pr_id": pr_id,
                "coverage_before": coverage_before,
                "coverage_after": coverage_after,
                "generated": generated_all,
                "iteration": iteration,
                "max_iterations": max_iterations,
                "post_generation_build_success": post_gen_run.get("build_success"),
            },
        )
        logger.info(
            "Reviewer verdict: should_continue=%s target_met=%s report=%s",
            review_result.get("should_continue"),
            review_result.get("target_met"),
            review_result.get("report_path"),
        )

        if mode == "pr" and review_result.get("pr_comment"):
            await asyncio.to_thread(
                get_pr_connector().post_comment, pr_id, review_result["pr_comment"]
            )

        _emit(progress_cb, "reviewer_done", result=review_result)

        if not review_result.get("should_continue"):
            _emit(progress_cb, "pipeline_done", result=review_result)
            return review_result

    final_result = {"status": "stopped_no_targets", "coverage_after": coverage_after}
    _emit(progress_cb, "pipeline_done", result=final_result)
    return final_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic QA Pipeline demo")
    parser.add_argument("--mode", choices=["spec", "pr", "continuous"], default="spec")
    parser.add_argument("--pr", dest="pr_id", default=None)
    parser.add_argument(
        "--question",
        default="",
        help="Optional free-text question to ground RAG retrieval in spec mode.",
    )
    parser.add_argument(
        "--target-class",
        dest="target_class",
        default=None,
        help="Optional exact class label (e.g. 'StringBuilderWriter') to force "
        "the Planner to target, bypassing ranking entirely. Useful for demos "
        "when you want a deterministic, reliable target regardless of RAG/"
        "structural ranking (see REQUIREMENTS.md section 6a on the offline "
        "hash embedding fallback skewing ranking toward high-fan-in nodes).",
    )
    args = parser.parse_args()

    _start_agent_servers()

    if args.mode == "continuous":
        pr_connector = get_pr_connector()
        open_prs = pr_connector.fetch_open_prs()
        logger.info("Continuous mode: %d open PR(s) found.", len(open_prs))
        for pr in open_prs:
            asyncio.run(_run_pipeline("pr", pr.id, args.question, args.target_class))
        return

    result = asyncio.run(
        _run_pipeline(args.mode, args.pr_id, args.question, args.target_class)
    )
    print(json.dumps(result, indent=2))



if __name__ == "__main__":
    main()

