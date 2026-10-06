"""Generator Agent (FR-15, FR-16, FR-17): drafts JUnit5 test code for a
planned target via Azure OpenAI, validates it through Guardrails AI, and
retries with corrective feedback on failure up to a bounded number of
attempts before giving up on that target.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.a2a_common import build_agent_app, build_agent_card  # noqa: E402
from config.settings import settings  # noqa: E402
from mcp_servers import graphify_mcp_server as graphify_tools  # noqa: E402
from qa_guardrails.test_code_guard import validate_generated_test  # noqa: E402

logger = logging.getLogger(__name__)

AGENT_URL = "http://127.0.0.1:8802/"

SYSTEM_PROMPT = (
    "You are an expert Java test engineer. Given a target class/method from "
    "the org.json library, write a single JUnit4 test class with one @Test "
    "method that exercises the described scenario. Rules:\n"
    "- This project uses JUnit4 (junit:junit:4.13.2), NOT JUnit5. You MUST "
    "import 'org.junit.Test' and 'static org.junit.Assert.*' - never use "
    "'org.junit.jupiter.*' imports or APIs (they are not on this project's "
    "classpath and will fail to compile).\n"
    "- Package must be org.json.junit.\n"
    "- Class name must end with 'Test'.\n"
    "- The @Test method name MUST start with the literal word 'test'.\n"
    "- Only reference classes/methods that are part of the standard JDK, "
    "JUnit4 (org.junit.*), or org.json (never invent new classes or methods, "
    "and never invent JSON-java methods that don't exist).\n"
    "- No System.exit, no process spawning, no network I/O.\n"
    "- Output ONLY the raw Java source code, no markdown fences, no prose."
)


def _call_azure_openai(user_prompt: str) -> str:
    cfg = settings.azure_openai
    if not cfg.is_configured:
        raise RuntimeError(
            "Azure OpenAI is not configured (AZURE_OPENAI_ENDPOINT/API_KEY/"
            "DEPLOYMENT). Cannot generate test code."
        )
    client = settings.build_openai_client()
    resp = client.chat.completions.create(
        model=cfg.deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_completion_tokens=2000,
    )
    return resp.choices[0].message.content or ""


def _build_prompt(target: dict, rationale_context: str, feedback: str = "") -> str:
    prompt = (
        f"Target: {target.get('label')} in {target.get('source_file')}\n"
        f"Rationale for testing: {target.get('rationale')}\n"
        f"Context: {rationale_context}\n"
    )
    if feedback:
        prompt += (
            "\nYour previous attempt failed these checks - fix them and "
            f"resubmit the full corrected file:\n{feedback}\n"
        )
    return prompt


def generate_test(payload: dict) -> dict:
    """Handler for the Generator agent's A2A skill.

    payload = {
        "target": {...},            # one item from Planner's targets list
        "rationale_context": str,   # extra free-text context (e.g. spec text)
        "max_retries": int,
    }
    """
    target = payload["target"]
    rationale_context = payload.get("rationale_context", "")
    max_retries = payload.get("max_retries", settings.max_guardrail_retries)
    known_labels = set(graphify_tools.list_known_labels())
    class_methods = graphify_tools.get_class_methods()

    feedback = ""
    last_code = ""
    last_errors: list[str] = []
    for attempt in range(max_retries + 1):
        prompt = _build_prompt(target, rationale_context, feedback)
        code = _call_azure_openai(prompt).strip()
        code = code.removeprefix("```java").removeprefix("```").removesuffix("```").strip()
        last_code = code
        report = validate_generated_test(
            code, known_labels=known_labels, class_methods=class_methods
        )
        if report.passed:
            class_name = _extract_class_name(code) or "GeneratedTest"
            class_name, code = _dedupe_class_name(class_name, code)
            return {
                "status": "accepted",
                "attempts": attempt + 1,
                "class_name": class_name,
                "relative_path": f"org/json/junit/{class_name}.java",
                "code": code,
            }
        last_errors = report.errors
        feedback = "\n".join(last_errors)
        logger.info("Guardrail rejection (attempt %d): %s", attempt + 1, feedback)

    return {
        "status": "rejected",
        "attempts": max_retries + 1,
        "errors": last_errors,
        "last_code": last_code,
    }


def _extract_class_name(code: str) -> str | None:
    import re

    m = re.search(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b", code)
    return m.group(1) if m else None


def _dedupe_class_name(class_name: str, code: str) -> tuple[str, str]:
    """Renames the generated class (and its source) if a file with that name
    already exists in the SUT's test tree, to avoid the class of destructive
    collision found during validation (a generated `JSONArrayTest` silently
    overwrote the SUT's real, pre-existing 52-test `JSONArrayTest.java`).
    write_test_file() also independently refuses same-name overwrites as a
    second line of defense.

    IMPORTANT: the disambiguating suffix is inserted BEFORE the trailing
    "Test" (e.g. StringBuilderWriterTest -> StringBuilderWriterAgent2Test),
    never appended after it. Maven Surefire's default include pattern only
    matches classes ending in Test/Tests/TestCase (or starting with Test) -
    an earlier version of this function produced names like
    `StringBuilderWriterTestAgent2`, which do NOT match that pattern and
    were silently never executed by `mvn test` at all (confirmed during
    validation: the class compiled cleanly, ran fine standalone via
    `-Dtest=`, but Surefire skipped it in the full suite - so coverage never
    moved even though the generated assertions were correct).
    """
    import re

    test_dir = settings.sut_dir / "src" / "test" / "java" / "org" / "json" / "junit"

    def make_candidate(base: str, suffix: int) -> str:
        if suffix == 1:
            return base
        if base.endswith("Test"):
            return f"{base[:-len('Test')]}Agent{suffix}Test"
        return f"{base}Agent{suffix}"

    candidate = class_name
    suffix = 1
    while (test_dir / f"{candidate}.java").exists():
        suffix += 1
        candidate = make_candidate(class_name, suffix)
    if candidate != class_name:
        code = re.sub(rf"\bclass\s+{re.escape(class_name)}\b", f"class {candidate}", code, count=1)
    assert (
        candidate.endswith(("Test", "Tests", "TestCase")) or candidate.startswith("Test")
    ), (
        f"Generated class name {candidate!r} does not match Maven Surefire's "
        "default test-discovery pattern (must end with Test/Tests/TestCase "
        "or start with Test) - it would silently never be executed."
    )
    return candidate, code


agent_card = build_agent_card(
    name="TestGeneratorAgent",
    description="Generates guardrail-validated JUnit5 tests via Azure OpenAI.",
    url=AGENT_URL,
    skill_id="generate_test",
    skill_description="Given a planned target, returns guardrail-passing JUnit5 test code.",
    tags=["qa", "generation", "guardrails"],
)
app = build_agent_app(agent_card, generate_test)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8802)
