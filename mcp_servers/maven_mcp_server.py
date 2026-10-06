"""MCP server exposing Maven/JaCoCo build & coverage tools (FR-18, FR-19).

Wraps `mvn test` (with JaCoCo already wired into sut/pom.xml - see
REQUIREMENTS.md section 10) and parses the resulting jacoco.xml coverage
report into a simple per-class + overall summary that agents can diff
run-over-run (FR-19, FR-23).
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from lxml import etree
from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)

server = MCPServer(name="maven-mcp", version="0.1.0")

MVN_CMD = settings.maven_home / "bin" / "mvn.cmd"
JACOCO_XML = settings.sut_dir / "target" / "site" / "jacoco" / "jacoco.xml"


def _mvn_env() -> dict:
    import os

    env = os.environ.copy()
    if settings.java_home:
        env["JAVA_HOME"] = settings.java_home
    return env


@server.tool()
def run_tests() -> dict:
    """Runs `mvn test` (with JaCoCo prepare-agent + report bound to the test
    phase) against the SUT (FR-18). Returns the raw Maven summary; use
    get_coverage_report() afterwards to read structured coverage.
    """
    proc = subprocess.run(
        [str(MVN_CMD), "test", "-B"],
        cwd=str(settings.sut_dir),
        capture_output=True,
        text=True,
        timeout=900,
        env=_mvn_env(),
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-6000:],
        "stderr": proc.stderr[-2000:],
        "build_success": proc.returncode == 0,
    }


@server.tool()
def write_test_file(relative_path: str, content: str, overwrite: bool = False) -> dict:
    """Writes a generated JUnit test file into the SUT's test source tree
    (used by the Generator agent after guardrails pass, FR-16/FR-18).
    `relative_path` is relative to sut/src/test/java, e.g.
    'org/json/junit/CDLTrailingBlankLineTest.java'.

    Refuses to silently overwrite a pre-existing test file (e.g. an
    already-present hand-written test class with the same generated name -
    this happened during validation: the Generator produced a class named
    `JSONArrayTest`, which collided with and destroyed the SUT's real,
    52-test `JSONArrayTest.java`). Pass overwrite=True to explicitly allow
    replacing an existing file.
    """
    target = settings.sut_dir / "src" / "test" / "java" / relative_path
    if target.exists() and not overwrite:
        return {
            "error": (
                f"Refusing to overwrite existing test file: {target}. "
                "Choose a different class name or pass overwrite=True."
            ),
            "path": str(target),
            "collision": True,
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": str(target), "collision": False}


@server.tool()
def check_compiles(relative_path: str) -> dict:
    """Dry-compiles the SUT's test sources (mvn test-compile, no tests run)
    and reports whether the given `relative_path` file compiles cleanly.

    Guardrails AI's regex-based hallucination checks (NoHallucinatedAPIs)
    only catch invented class/method *names* - they miss invented method
    *signatures* on real APIs, e.g. calling a real class's constructor with
    the wrong argument type (found during validation: the Generator called
    `new StringBuilderWriter(aStringBuilder)`, but the real constructor only
    accepts `int` or no args - a type-mismatch, not a missing symbol). A
    real `javac` compile via Maven catches this whole class of hallucination
    generically. Call this after write_test_file() and before accepting a
    generated test as final (FR-16 defense-in-depth).
    """
    proc = subprocess.run(
        [str(MVN_CMD), "test-compile", "-B"],
        cwd=str(settings.sut_dir),
        capture_output=True,
        text=True,
        timeout=300,
        env=_mvn_env(),
    )
    success = proc.returncode == 0
    relevant_errors = []
    if not success:
        target_name = Path(relative_path).name
        for line in proc.stdout.splitlines():
            if "[ERROR]" in line and target_name in line:
                relevant_errors.append(line.strip())
        if not relevant_errors:
            # Compile failure elsewhere (e.g. a different generated file in
            # the same batch) - still surface it, just not attributed to
            # this specific file.
            relevant_errors = [
                line.strip() for line in proc.stdout.splitlines() if "[ERROR]" in line
            ][:10]
    return {
        "compiles": success,
        "errors": relevant_errors,
        "stdout_tail": proc.stdout[-3000:] if not success else "",
    }



def _counter_dict(elem) -> dict:
    counters = {}
    for c in elem.findall("counter"):
        counters[c.get("type")] = {
            "missed": int(c.get("missed", 0)),
            "covered": int(c.get("covered", 0)),
        }
    return counters


def _pct(counter: dict) -> float:
    missed = counter.get("missed", 0)
    covered = counter.get("covered", 0)
    total = missed + covered
    return round((covered / total) * 100, 2) if total else 0.0


@server.tool()
def get_coverage_report() -> dict:
    """Parses sut/target/site/jacoco/jacoco.xml into a structured summary:
    overall LINE/BRANCH/INSTRUCTION coverage % and a per-class breakdown
    (FR-19). Returns an error dict if the report doesn't exist yet (run
    run_tests() first).
    """
    if not JACOCO_XML.exists():
        return {"error": f"jacoco.xml not found at {JACOCO_XML}. Run run_tests() first."}

    tree = etree.parse(str(JACOCO_XML))
    root = tree.getroot()

    overall = _counter_dict(root)
    classes = []
    for pkg in root.findall("package"):
        for cls in pkg.findall("class"):
            counters = _counter_dict(cls)
            classes.append(
                {
                    "class": cls.get("name", "").replace("/", "."),
                    "line_pct": _pct(counters.get("LINE", {})),
                    "branch_pct": _pct(counters.get("BRANCH", {})),
                    "instruction_pct": _pct(counters.get("INSTRUCTION", {})),
                    "counters": counters,
                }
            )

    return {
        "overall_line_pct": _pct(overall.get("LINE", {})),
        "overall_branch_pct": _pct(overall.get("BRANCH", {})),
        "overall_instruction_pct": _pct(overall.get("INSTRUCTION", {})),
        "classes": sorted(classes, key=lambda c: c["line_pct"]),
    }


if __name__ == "__main__":
    server.run(transport="stdio")
