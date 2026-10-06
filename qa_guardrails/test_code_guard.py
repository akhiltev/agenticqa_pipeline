"""Guardrails AI validators for generated JUnit test code (FR-16).

NOTE: this local package is named `qa_guardrails` (not `guardrails`) to avoid
shadowing the installed `guardrails-ai` PyPI package, since this project's
root directory is on `sys.path` when scripts are run from here.

Checks applied before generated code is written to disk / executed:
  1. Valid Java syntax (brace/paren balance dry check; a real `javac -Xlint`
     compile check is performed later by the MCP maven tool before `mvn test`
     actually runs, since that requires the full classpath).
  2. No references to APIs/classes/methods absent from the Graphify graph
     (hallucination guard).
  3. Test method naming convention: `test<Method>_<Scenario>` (case-insensitive
     "test" prefix on any @Test method).
  4. No unsafe side effects (System.exit, unrestricted file/network I/O).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from guardrails import Guard
from guardrails.validator_base import FailResult, PassResult, Validator, register_validator

# Keep the demo fully offline-capable; tracing telemetry requires network egress.
from guardrails.settings import settings as _guardrails_settings

_guardrails_settings.disable_tracing = True

UNSAFE_PATTERNS = [
    re.compile(r"System\s*\.\s*exit\s*\("),
    re.compile(r"Runtime\s*\.\s*getRuntime\s*\(\s*\)\s*\.\s*exec\s*\("),
    re.compile(r"new\s+ProcessBuilder\s*\("),
    re.compile(r"new\s+Socket\s*\("),
    re.compile(r"java\.net\.http\.HttpClient"),
]

TEST_METHOD_RE = re.compile(
    r"@Test\b[^;{]*?\bvoid\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.DOTALL,
)

JUNIT5_IMPORT_RE = re.compile(r"\borg\.junit\.jupiter\b")


@dataclass
class GuardrailReport:
    passed: bool
    errors: list[str] = field(default_factory=list)


@register_validator(name="qa/balanced-braces", data_type="string")
class BalancedBraces(Validator):
    """FR-16: dry syntax sanity check (brace/paren balance)."""

    def _validate(self, value: Any, metadata: dict) -> Any:
        text = str(value)
        for open_c, close_c, label in (("{", "}", "braces"), ("(", ")", "parens")):
            depth = 0
            for ch in text:
                if ch == open_c:
                    depth += 1
                elif ch == close_c:
                    depth -= 1
                if depth < 0:
                    return FailResult(error_message=f"Unbalanced {label}: unexpected '{close_c}'.")
            if depth != 0:
                return FailResult(error_message=f"Unbalanced {label}: {depth} unclosed '{open_c}'.")
        return PassResult()


@register_validator(name="qa/no-unsafe-side-effects", data_type="string")
class NoUnsafeSideEffects(Validator):
    """FR-16: no System.exit / process spawning / raw network I/O."""

    def _validate(self, value: Any, metadata: dict) -> Any:
        text = str(value)
        for pattern in UNSAFE_PATTERNS:
            if pattern.search(text):
                return FailResult(
                    error_message=f"Unsafe side effect detected matching /{pattern.pattern}/."
                )
        return PassResult()


@register_validator(name="qa/test-naming-convention", data_type="string")
class TestNamingConvention(Validator):
    """FR-16: every @Test method must start with 'test' (case-insensitive) -
    a lightweight convention check suitable for a demo guardrail."""

    def _validate(self, value: Any, metadata: dict) -> Any:
        text = str(value)
        methods = TEST_METHOD_RE.findall(text)
        if not methods:
            return FailResult(error_message="No @Test method found in generated code.")
        bad = [m for m in methods if not m.lower().startswith("test")]
        if bad:
            return FailResult(
                error_message=(
                    "Test method(s) do not follow naming convention "
                    f"(must start with 'test'): {bad}"
                )
            )
        return PassResult()


@register_validator(name="qa/no-hallucinated-apis", data_type="string")
class NoHallucinatedAPIs(Validator):
    """FR-16: flags identifiers/calls that look like SUT class or method
    references but are not present in the Graphify knowledge graph
    (hallucination guard).

    `known_labels` (a flat set of class/method labels) catches invented
    *class* names (e.g. `new FooBarBaz()`). `class_methods` (a
    {ClassName: [methodName, ...]} map derived from the graph's "method"
    edges - see graphify_mcp_server.get_class_methods()) additionally
    catches invented *method* calls on a real class, e.g.
    `JSONArray.toJSONArray(...)`, where `toJSONArray` is a real method name
    in the codebase but is actually only defined on `CDL`/`JSONObject`/
    `JSONML`, not on `JSONArray`. This second check was added after that
    exact case slipped through validation and failed to compile.
    """

    def _validate(self, value: Any, metadata: dict) -> Any:
        known_labels: set = metadata.get("known_labels", set())
        class_methods: dict = metadata.get("class_methods", {})
        text = str(value)

        errors = []

        if known_labels:
            referenced = set(re.findall(r"\bnew\s+([A-Z][A-Za-z0-9_]*)\s*\(", text))
            referenced |= set(re.findall(r"\borg\.json\.([A-Z][A-Za-z0-9_]*)\b", text))
            unknown = {r for r in referenced if r not in known_labels}
            if unknown:
                errors.append(
                    f"Referenced class(es) not found in Graphify knowledge graph: {sorted(unknown)}"
                )

        if class_methods:
            calls = re.findall(r"\b([A-Z][A-Za-z0-9_]*)\.([a-zA-Z_][A-Za-z0-9_]*)\s*\(", text)
            bad_calls = [
                f"{cls}.{method}()"
                for cls, method in calls
                if cls in class_methods and method not in class_methods[cls]
                # skip constructs that look like Class.method() but are
                # actually chained calls on a preceding expression, e.g.
                # `foo.getJSONArray(0).toJSONArray` - only flag when `cls`
                # is itself a known SUT/JDK class name we have data for.
            ]
            if bad_calls:
                errors.append(
                    "Called method(s) not found on the referenced class in the "
                    f"Graphify knowledge graph: {sorted(set(bad_calls))}"
                )

        if errors:
            return FailResult(error_message="; ".join(errors))
        return PassResult()



@register_validator(name="qa/no-junit5-apis", data_type="string")
class NoJUnit5APIs(Validator):
    """FR-16 (project-specific): this SUT (JSON-java) declares JUnit4 as its
    only test dependency in pom.xml. Generated tests using JUnit5
    (org.junit.jupiter.*) compile-fail since that package isn't on the
    classpath - this guardrail catches that class of hallucination/mismatch
    before the code is ever written to disk or built.
    """

    def _validate(self, value: Any, metadata: dict) -> Any:
        text = str(value)
        if JUNIT5_IMPORT_RE.search(text):
            return FailResult(
                error_message=(
                    "Generated code references org.junit.jupiter (JUnit5), but "
                    "this project only has JUnit4 (junit:junit) on its "
                    "classpath. Use 'org.junit.Test' and "
                    "'static org.junit.Assert.*' instead."
                )
            )
        return PassResult()


def build_test_code_guard() -> Guard:
    """Builds the composed Guard used by the Generator agent (FR-16)."""
    return Guard().use_many(
        BalancedBraces(on_fail="exception"),
        NoUnsafeSideEffects(on_fail="exception"),
        TestNamingConvention(on_fail="exception"),
        NoHallucinatedAPIs(on_fail="exception"),
        NoJUnit5APIs(on_fail="exception"),
    )


def validate_generated_test(
    code: str,
    known_labels: set | None = None,
    class_methods: dict | None = None,
) -> GuardrailReport:
    """Runs all guardrails against `code`, returning a structured report
    instead of raising, so the Generator agent can decide on retry logic
    (FR-17) without try/except control flow at the call site.
    """
    metadata = {
        "known_labels": known_labels or set(),
        "class_methods": class_methods or {},
    }
    errors: list[str] = []
    for validator in (
        BalancedBraces(),
        NoUnsafeSideEffects(),
        TestNamingConvention(),
        NoHallucinatedAPIs(),
        NoJUnit5APIs(),
    ):
        result = validator._validate(code, metadata)
        if isinstance(result, FailResult):
            errors.append(result.error_message)
    return GuardrailReport(passed=not errors, errors=errors)



