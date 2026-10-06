"""Manages background AI QA Engineer pipeline runs (run_demo._run_pipeline)
and streams their progress events to the UI via Server-Sent Events.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_demo  # noqa: E402


@dataclass
class RunState:
    run_id: str
    status: str = "running"  # running | done | error
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)


_RUNS: dict[str, RunState] = {}


def start_run(
    mode: str,
    question: str = "",
    target_class: str | None = None,
    pr_id: str | None = None,
) -> str:
    run_id = uuid.uuid4().hex[:12]
    state = RunState(run_id=run_id)
    _RUNS[run_id] = state

    def progress_cb(event: dict[str, Any]) -> None:

        # progress_cb is always invoked directly on the main event-loop
        # thread (run_demo._run_pipeline only calls it from its own async
        # body, never from inside an asyncio.to_thread(...) worker), so we
        # enqueue synchronously here rather than via loop.call_soon_threadsafe.
        # call_soon_threadsafe merely *schedules* the put_nowait for a later
        # event-loop callback tick, which raced with (and lost to) the
        # "__stream_end__" sentinel enqueued right after the pipeline
        # coroutine returns below - causing the final "reviewer_done"/
        # "pipeline_done" events (and therefore the Run tab's "Done" step)
        # to never reach the SSE stream.
        state.events.append(event)
        state.queue.put_nowait(event)

    async def _run() -> None:
        await asyncio.to_thread(run_demo._start_agent_servers)
        try:

            result = await run_demo._run_pipeline(
                mode, pr_id, question, target_class, progress_cb=progress_cb
            )
            state.result = result
            state.status = "done"
        except Exception as exc:  # noqa: BLE001
            state.status = "error"
            state.error = str(exc)
        finally:
            await state.queue.put({"type": "__stream_end__"})

    asyncio.create_task(_run())
    return run_id


def get_run(run_id: str) -> RunState | None:
    return _RUNS.get(run_id)


async def stream_events(run_id: str):
    state = _RUNS.get(run_id)
    if state is None:
        yield {"type": "error", "message": f"Unknown run_id {run_id!r}"}
        return
    while True:
        event = await state.queue.get()
        if event.get("type") == "__stream_end__":
            yield {
                "type": "stream_end",
                "status": state.status,
                "result": state.result,
                "error": state.error,
            }
            return
        yield event
