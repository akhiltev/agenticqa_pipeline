"""Wraps reset_demo_state.py's functions for the UI's Reset button, so
POST /api/reset runs exactly the same, already-validated logic as the CLI
script (not a reimplementation).
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import reset_demo_state  # noqa: E402


def reset(baseline_build: bool = True, keep_reports: bool = False) -> dict:
    buf = io.StringIO()
    with redirect_stdout(buf):
        print("Resetting demo state to a clean 'before' snapshot...\n")
        if not keep_reports:
            reset_demo_state.reset_reports()
        reset_demo_state.reset_rag()
        reset_demo_state.reset_graphify()
        reset_demo_state.reset_maven_build()
        reset_demo_state.restore_sut_git_state()
        if baseline_build:
            reset_demo_state.run_baseline_build()
        print("\nDone. Repo is now in a clean 'before' state.")
    return {"log": buf.getvalue()}
