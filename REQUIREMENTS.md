# Agentic QA Pipeline — Demo Requirements

**Status:** Approved plan, pending implementation
**Last updated:** 2026-09-03

## 1. Vision / Demo Story

Build a demo "AI QA Engineer" ecosystem that, given (a) a feature spec / requirements
source and (b) a real codebase, autonomously:

1. Plans relevant test cases (using structural code knowledge + requirements context).
2. Generates test code.
3. Validates the generated code against guardrails before it is ever executed.
4. Executes the tests and measures code coverage.
5. Iterates (plan → generate → validate → execute) until a coverage target is met or an
   iteration budget is exhausted.
6. Produces a human-readable QA report.

The pipeline must also demonstrate **continuous enhancement**: it can be re-triggered
against a pull request (PR) + its linked requirement/work item, scope itself to just the
diff, and show the automation suite's coverage improving run over run.

## 2. Core Technologies & Their Roles

| Technology | Role |
|---|---|
| **Google A2A (Agent2Agent protocol)** | Wire protocol for agent-to-agent task delegation and discovery (Agent Cards) between Orchestrator, Planner, Generator, and Reviewer agents. |
| **MCP (Model Context Protocol)** | Standardized tool access for agents — e.g. querying the Graphify knowledge graph, running Maven/JaCoCo, reading/writing files. |
| **Graphify** (Graphify-Labs/graphify) | Deterministic AST-based knowledge graph extraction from the codebase (no vector store) — gives agents exact structural context (classes, methods, call/dependency edges) to plan tests and to guard against hallucinated APIs. |
| **RAG (Retrieval-Augmented Generation)** | Semantic retrieval over unstructured requirements content (specs, Jira/Azure Boards work items) to ground test planning in acceptance criteria. |
| **Guardrails AI** | Validates LLM-generated test code before execution: syntax validity, no hallucinated APIs (cross-checked against the Graphify graph), naming conventions, no unsafe side effects. |
| **JaCoCo** | Java code-coverage instrumentation; produces before/after coverage deltas that drive the iterate/stop decision and the final report. |
| **Azure OpenAI** | LLM backend for all agents (Planner, Generator, Reviewer). |
| **Chroma** | Local, file-based vector store backing the RAG layer. |

## 3. Key Design Decisions (from planning discussion)

| Decision point | Choice |
|---|---|
| Primary demo story | Full "AI QA engineer" workflow: spec-in (RAG) + codebase-in (Graphify KG) → plan → generate → execute → measure coverage → report out |
| Language/stack | Polyglot: Python orchestration/agents + real A2A Python SDK + real MCP servers; Java sample app as the system under test (SUT) |
| LLM backend | Azure OpenAI (endpoint/key/deployment via environment variables) |
| Guardrails framework | Guardrails AI (guardrails-hub, Pydantic-based validators) |
| Vector store | Chroma (local, file-based, zero setup) |
| System under test (SUT) | A real open-source Java repo, chosen by Cline: **stleary/JSON-java** (small, low-dependency, Maven-based, ~30–40 classes — enough uncovered branches to be interesting, small enough to stay comprehensible in a demo) |
| Requirements tracker integration | Mocked by default (fixture-based, no credentials required); one tracker gets a **fully real, wired connector**: **Azure Boards** (Azure DevOps Work Items REST API) |
| PR host integration | Mocked by default (fixture-based); one host gets a **fully real, wired connector**: **Azure Repos** (Azure DevOps Git Pull Requests REST API), sharing the same Azure DevOps PAT as Azure Boards |
| Deferred/stubbed integrations | Jira Cloud connector and GitHub PR connector are defined behind the same interfaces but left as documented stubs (`NotImplementedError` + TODO) for future work |
## 4. Functional Requirements

### 4.1 Knowledge Graph Extraction
- FR-1: The system SHALL run `graphify extract` against the SUT (`sut/`, JSON-java) to
  produce a deterministic AST-based knowledge graph (`graphify_out/graph.json`).
- FR-2: The Planner agent SHALL be able to query the graph via an MCP tool (e.g. list
  classes/methods, find low-coverage/high-risk structural targets, list edges for a
  given node).
- FR-3: On PR-triggered runs, extraction/queries SHALL be scoped to the files touched by
  the PR diff where feasible (incremental context, not a full re-plan of the whole repo).

### 4.2 Requirements Ingestion (RAG)
- FR-4: The system SHALL support a `REQUIREMENTS_SOURCE` setting with values `mock`
  (default), `azure_boards`, and `jira` (stub only).
- FR-5: All requirements connectors SHALL implement a common interface
  (`fetch_items()`, `fetch_item(id)`) and normalize output (title, description,
  acceptance criteria, tags/links) into a common chunk schema for embedding.
- FR-6: Normalized requirement chunks SHALL be embedded (Azure OpenAI embeddings) and
  indexed into a local Chroma store, incrementally upsertable per item.
- FR-7: The `mock` connector SHALL ship 3–5 realistic fixture work items
  (`fixtures/work_items.json`) requiring no external accounts or credentials.
- FR-8: The `azure_boards` connector SHALL authenticate via a Personal Access Token
  (PAT) and fetch real work items from Azure DevOps using the WIQL + Work Items REST
  API (api-version 7.1).

### 4.3 PR Ingestion
- FR-9: The system SHALL support a `PR_SOURCE` setting with values `mock` (default),
  `azure_repos`, and `github` (stub only).
- FR-10: All PR connectors SHALL implement a common interface (`fetch_pr(id)`,
  `fetch_open_prs()`, `post_comment(id, text)`).
- FR-11: The `mock` connector SHALL ship a fixture PR (`fixtures/sample_pr.json`)
  containing a realistic diff against 1–2 SUT files, linked to a mock work item ID.
- FR-12: The `azure_repos` connector SHALL authenticate using the same Azure DevOps PAT
  as the `azure_boards` connector and fetch PR diffs and post PR comments via the Azure
  DevOps Git REST API.

### 4.4 Test Planning
- FR-13: The Planner agent SHALL combine (a) structural context from the Graphify
  graph and (b) semantically retrieved requirement chunks from Chroma to produce a
  ranked list of test targets (class/method, rationale, priority).
- FR-14: In PR mode, the Planner SHALL prioritize targets that cover new/changed
  branches in the diff and targets that verify the linked work item's acceptance
  criteria.

### 4.5 Test Generation
- FR-15: The Generator agent SHALL call Azure OpenAI to draft JUnit5 test code for each
  planned target.
- FR-16: Generated code SHALL pass through Guardrails AI validators before being
  written to disk:
  - valid Java syntax (dry compile check),
  - no references to APIs/classes/methods absent from the Graphify graph
    (hallucination guard),
  - test method naming convention compliance,
  - no unsafe side effects (e.g. `System.exit`, unrestricted file/network I/O).
- FR-17: On guardrail failure, the Generator SHALL retry with corrective feedback up
  to a bounded number of attempts before skipping that target and logging the failure.

### 4.6 Test Execution & Coverage
- FR-18: The Executor (via an MCP tool) SHALL run `mvn test` with JaCoCo instrumentation
  against the SUT and parse the resulting coverage report (XML).
- FR-19: The system SHALL compute coverage deltas (before/after) at module/class
  granularity.

### 4.7 Review & Reporting
- FR-20: The Reviewer agent SHALL decide, based on coverage deltas and iteration
  budget, whether to loop back to the Planner for additional targets or finalize.
- FR-21: The Reviewer SHALL produce a human-readable Markdown QA report
  (`reports/qa_report_<timestamp>.md`) summarizing targets tested, coverage before/after,
  guardrail rejections, and pass/fail results.
- FR-22: In PR mode, the Reviewer SHALL additionally produce a PR-comment-style summary,
  posted via the PR connector's `post_comment` (or printed/saved when running in mock
  mode).
- FR-23: The system SHALL maintain a cross-run ledger (`reports/suite_health.json`)
  tracking per-module coverage % over time to demonstrate continuous improvement.

### 4.8 Orchestration Modes
- FR-24: `run_demo.py --mode=spec` SHALL run the original spec-driven, full-suite
  planning flow using static files in `specs/`.
- FR-25: `run_demo.py --mode=pr --pr=<id>` SHALL run the PR-scoped flow using the
  configured PR/requirements connectors.
- FR-26: `run_demo.py --mode=continuous` SHALL iterate once over all open PRs returned
  by the PR connector, applying the PR-scoped flow to each.

## 5. Non-Functional Requirements

- NFR-1: The default demo run (mock connectors, no external credentials) SHALL be fully
  runnable offline aside from the Azure OpenAI calls.
- NFR-2: All A2A messages and MCP tool calls SHALL be logged/traceable to the console
  for live demo narration.
- NFR-3: Real connectors (Azure Boards, Azure Repos) SHALL be swappable via config only
  (`REQUIREMENTS_SOURCE`, `PR_SOURCE`) with no code changes required elsewhere.
- NFR-4: Stubbed connectors (Jira, GitHub) SHALL raise a clear `NotImplementedError`
  with a TODO comment describing the expected implementation, so they can be completed
  later without redesigning the interface.
- NFR-5: Secrets (Azure OpenAI keys, Azure DevOps PAT) SHALL be supplied via environment
  variables only, never committed; a `.env.example` SHALL document all required
  variables with placeholder values.
- NFR-6: The pipeline SHALL bound its iteration loop (max iterations, max retries per
  guardrail failure) to guarantee termination in a demo timeframe.

## 6. Environment Variables (`.env.example`)

```
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=

# Requirements / PR connector selection
REQUIREMENTS_SOURCE=mock            # mock | azure_boards | jira
PR_SOURCE=mock                      # mock | azure_repos | github

# Azure DevOps (used by both azure_boards and azure_repos connectors)
AZURE_DEVOPS_PAT=
AZURE_DEVOPS_ORG=
AZURE_DEVOPS_PROJECT=
AZURE_DEVOPS_REPO=
```

> **Update (validated 2026-09-04):** the resource actually used for this demo
> (`ai-0500-foundry.services.ai.azure.com`, an Azure AI Foundry-style
> resource) does **not** use the classic dated `api-version` +
> `/openai/deployments/{name}` routing that `AZURE_OPENAI_API_VERSION` and
> the SDK's `AzureOpenAI` client assume. It uses the unified
> `{endpoint}/openai/v1/...` surface with **no dated api-version** required.
> The code was updated accordingly (see `agents/generator_agent.py` /
> `rag/index_specs.py`, which now build the client as
> `OpenAI(base_url=f"{endpoint}/openai/v1", api_key=..., default_headers={"api-key": ...})`
> instead of `AzureOpenAI(...)`.
> Chat completion against deployment `gpt-5.2` was confirmed working
> end-to-end. **Embeddings are not yet working**: no deployment under
> `text-embedding-3-small` (or common alternate names) exists on this
> resource — confirmed via `DeploymentNotFound` on the same
> `/openai/v1/embeddings` path. This must be created in Azure AI Foundry
> (deploy an embedding model, e.g. `text-embedding-3-small`, and note the
> exact deployment name) before RAG can use live semantic embeddings; until
> then RAG automatically falls back to the offline hash embedding (NFR-1),
> which is functionally fine for the demo but not semantically meaningful.
> Validate any Azure OpenAI config change with `python validate_azure_openai.py`.

## 6a. Real Findings From Live-LLM Validation (2026-09-16)

Running the full pipeline against the real Azure OpenAI endpoint surfaced
several genuine gaps, all now fixed:

- **Client construction**: `settings.build_openai_client()` (config/settings.py)
  centralizes the correct client construction for this Azure AI Foundry-style
  resource (plain `OpenAI` client, `base_url={endpoint}/openai/v1`, `api-key`
  header) - both `agents/generator_agent.py` and `rag/index_specs.py` now use
  it instead of instantiating `AzureOpenAI` directly.
- **Embedding fallback robustness**: `_AzureOpenAIEmbeddingFunction.__init__`
  now eagerly probes the embeddings deployment with a real call, so a
  `DeploymentNotFound` (or any other misconfiguration) is caught at
  initialization and triggers the offline hash fallback, instead of crashing
  the pipeline the first time a document is actually embedded mid-run.
- **A2A client timeout**: `agents/a2a_client.py`'s `call_agent()` now uses a
  180s `httpx.AsyncClient` timeout (via `ClientConfig.httpx_client`), since
  the SDK's default is far too short for a real LLM call happening inside
  the Generator agent's A2A task.
- **JUnit version mismatch**: the SUT (JSON-java) only declares JUnit4
  (`junit:junit:4.13.2`) in `pom.xml`, but the Generator's original system
  prompt said "JUnit5", so the LLM produced `org.junit.jupiter.*` imports
  that don't compile. Fixed the prompt (agents/generator_agent.py) and added
  a dedicated `NoJUnit5APIs` guardrail (qa_guardrails/test_code_guard.py) as
  defense-in-depth.
- **Destructive filename collision (critical)**: the Generator produced a
  class named `JSONArrayTest`, which collided with and *silently overwrote*
  the SUT's real, pre-existing 52-test `JSONArrayTest.java` on disk via
  `write_test_file()`. Fixed two ways: (1) `write_test_file()`
  (mcp_servers/maven_mcp_server.py) now refuses to overwrite an existing
  file unless `overwrite=True` is explicitly passed, returning a
  `{"collision": True, "error": ...}` result instead; (2) the Generator
  agent (`_dedupe_class_name`) proactively renames the generated class if a
  same-named file already exists in the SUT's test tree, before ever
  calling `write_test_file()`.
- **Method-level hallucination guard gap**: the original `NoHallucinatedAPIs`
  guardrail only checked class-name references (`new Foo()` / `org.json.Foo`),
  so it missed a real hallucinated call, `JSONArray.toJSONArray(...)` -
  `toJSONArray` is a real method name in the codebase, but is only defined on
  `CDL`/`JSONObject`/`JSONML`, not on `JSONArray`. Added
  `graphify_mcp_server.get_class_methods()` (derives a
  `{ClassName: [methodName, ...]}` map from the graph's "method" edges) and
  extended `NoHallucinatedAPIs` to cross-check `Class.method(` call sites
  against it.
- **Stale coverage-after / false "target met" (critical)**: `run_demo.py`
  discarded `maven_tools.run_tests()`'s `build_success` flag after
  generation, so when a generated test's assertions genuinely failed (i.e.
  it correctly caught a real, pre-existing defect - `CDL.toJSONArray` truly
  does not skip trailing blank lines yet), `get_coverage_report()` still
  returned the last **successful** build's stale `jacoco.xml`, and the
  Reviewer reported a false `target_met: true`. Fixed: `run_demo.py` now
  passes `post_generation_build_success` to the Reviewer, which gates
  `target_met`/`should_continue` on it and renders a clear "⚠️ Build Failed
  After Generation" section in the QA report explaining that the numbers are
  stale and pointing at `sut/target/surefire-reports/`.
- **Chroma embedding-function persistence**: switching a collection between
  the offline hash embedding and the real Azure embedding function (or back)
  requires deleting `rag/chroma_store/` first - Chroma raises a hard error
  otherwise (`embedding function conflict: new vs persisted`), since the
  embedding function used to create a collection is treated as immutable
  metadata.
- **Demo-reset script wiped the JaCoCo plugin (critical)**: the first version
  of `reset_demo_state.py` ran `git checkout -- .` inside `sut/` to discard
  AI-generated test files, but that also reverted `sut/pom.xml`'s
  intentional, permanent JaCoCo plugin addition, silently breaking all
  future coverage reports (baseline build still succeeded, but
  `get_coverage_report()` returned all-zero numbers with no error). Fixed:
  `restore_sut_git_state()` now runs `git checkout -- src/test/java`
  (scoped only to test sources, never the whole repo) and explicitly checks
  `sut/pom.xml` for `jacoco-maven-plugin` afterward, printing a loud warning
  if it's ever missing.
- **Deduped test class names silently never ran (critical, root cause of
  "no coverage change" reports)**: `_dedupe_class_name()` in
  `agents/generator_agent.py` originally disambiguated colliding class
  names by *appending* a suffix after "Test", e.g.
  `StringBuilderWriterTest` -> `StringBuilderWriterTestAgent2`. Maven
  Surefire's default test-discovery pattern only matches classes ending in
  `Test`/`Tests`/`TestCase` (or starting with `Test`) - a name ending in
  `...TestAgent2` matches none of those. The result: these generated test
  files compiled cleanly, passed when run individually via
  `mvn test -Dtest=ClassName`, and were even accepted by the new
  `check_compiles()` dry-compile guardrail (which only checks compilation,
  not discovery) - but Surefire silently skipped them in every full
  `mvn test` run, so `jacoco.exec`/coverage never reflected them at all.
  This was the actual root cause behind several "generated 3 tests, 0
  coverage change" demo runs that were originally misdiagnosed as the
  tests just happening to hit already-covered lines. Fixed: the
  disambiguating suffix is now inserted *before* the trailing "Test" (e.g.
  `StringBuilderWriterAgent2Test`), plus an assertion that the final
  candidate name still matches Surefire's naming convention. Verified fix:
  a demo run against `StringBuilderWriter` after this fix produced 3
  correctly-named, Surefire-discovered tests, raising that class's own line
  coverage from 83.33% to 96.67% and overall repo coverage from 89.97% to
  90.10% (+0.13 pts) - the first genuinely coverage-increasing, fully
  successful run since this demo was built.
- **RAG ranking without real embeddings kept re-selecting "god nodes"**:
  with embeddings falling back to the offline hash function (no real
  embedding deployment - see above), RAG retrieval is not semantically
  meaningful, so the Planner's ranking heuristic
  (`agents/planner_agent.py:_rank_targets`) fell back almost entirely to
  structural graph fan-in, which reliably re-selected `CDL` (a high-fan-in
  "god node", 54 edges) as a top target regardless of the actual
  `--question` asked - even for completely unrelated questions like one
  about `StringBuilderWriter`. Mitigated two ways: (1) added a
  `--target-class` CLI flag to `run_demo.py` (threaded through to the
  Planner's `plan_targets` payload) that deterministically restricts
  targets to a single named class, bypassing ranking entirely - useful for
  reliable demos; (2) increased the RAG-match score bonus in
  `_rank_targets` from `5.0` to `50.0` (previously roughly comparable to
  ~5 edges of structural fan-in, now dominant) so that even an imperfect
  RAG match reliably outranks pure structural fan-in when there IS a
  relevant spec/work-item to retrieve.
- **Generated tests can hallucinate constructor/method call *signatures*,
  not just names**: Guardrails AI's `NoHallucinatedAPIs` regex checks only
  catch invented class/method *names* missing from the Graphify graph -
  they miss a real class/method existing but being called with the wrong
  argument types (found during validation: `new StringBuilderWriter(aStringBuilder)`
  when the real constructor only accepts `int` or no args). Added a new MCP
  tool, `maven_mcp_server.check_compiles(relative_path)`, which runs a real
  `mvn test-compile` after `write_test_file()` and before the Generator's
  result is treated as final; `run_demo.py` now deletes the file and marks
  the target `compile_failed` if this dry-compile fails, rather than
  discovering the problem only when the full `mvn test` run fails later.


## 7. Proposed Repository Layout

```
d:\agentic_qa_pipeline
├── sut/                              # cloned JSON-java (system under test)
├── graphify_out/                     # graph.json from `graphify extract`
├── specs/                            # markdown feature spec(s) for RAG (spec mode)
├── fixtures/
│   ├── work_items.json               # mock requirements fixtures
│   └── sample_pr.json                # mock PR fixture
├── connectors/
│   ├── requirements/
│   │   ├── base.py
│   │   ├── mock_connector.py
│   │   ├── azure_boards_connector.py # REAL
│   │   └── jira_connector.py         # STUB
│   └── prs/
│       ├── base.py
│       ├── mock_connector.py
│       ├── azure_repos_connector.py  # REAL
│       └── github_connector.py       # STUB
├── rag/
│   └── index_specs.py                # builds/updates Chroma index
├── mcp_servers/
│   ├── graphify_mcp_server.py
│   └── maven_mcp_server.py
├── agents/
│   ├── orchestrator_agent.py
│   ├── planner_agent.py
│   ├── generator_agent.py
│   └── reviewer_agent.py
├── guardrails/
│   └── test_code_guard.py            # NOTE: implemented as qa_guardrails/ to avoid
│                                      # shadowing the installed guardrails-ai package

├── config/
│   ├── agent_cards/*.json
│   └── settings.py
├── reports/
│   ├── qa_report_<timestamp>.md
│   └── suite_health.json
├── requirements.txt
├── run_demo.py
├── .env.example
├── REQUIREMENTS.md                   # this file
└── README.md
```

## 8. Out of Scope (for this demo)

- Fully real Jira Cloud and GitHub connectors (documented stubs only).
- Production-grade scheduling/webhooks for continuous polling (CLI-triggered modes only).
- Multi-repo or multi-language SUT support.
- Authentication/authorization hardening beyond environment-variable secrets.

## 9. Open Items / Future Follow-ups

- Wire real Jira Cloud connector behind `connectors/requirements/jira_connector.py`.
- Wire real GitHub PR connector behind `connectors/prs/github_connector.py`.
- Optional: replace CLI-triggered `continuous` mode with a real scheduler/webhook.
- Optional: swap SUT repo (pipeline is designed to be repo-agnostic).

## 10. Environment Setup Notes (validated during implementation)

These notes capture real findings from setting up this demo locally on Windows, since
they affect exact commands used in the implementation.

- **Python venv**: created with Python 3.12 (`.venv/`), since Python 3.14 (the default
  `python` on PATH) lacks wheels for some dependencies (e.g. chromadb's compiled deps).
  Always activate/run via `.venv\Scripts\python.exe` or `.venv\Scripts\pip.exe`.
- **Installed packages** (see `requirements.txt` / `installed_versions.txt`):
  `openai==2.54.0`, `a2a-sdk==1.1.2`, `mcp==2.1.1`, `chromadb==1.5.9`,
  `guardrails-ai==0.11.0`, `graphifyy==0.9.53` (PyPI name for the `graphify` CLI),
  `requests`, `python-dotenv`, `pydantic`, `lxml`.
- **Graphify CLI reality check**: the CLI does **not** have an `extract` subcommand (that
  was an assumption from initial planning). The actual relevant subcommands are:
  - `graphify update <path> --no-cluster` — deterministic AST-only extraction, **no LLM
    required**, writes `<path>/graphify-out/graph.json`. This is what our pipeline uses.
  - `graphify query "<question>"`, `graphify explain "X"`, `graphify god-nodes`,
    `graphify affected "X"`, `graphify path "A" "B"` — graph query utilities, useful
    building blocks for the `graphify_mcp_server.py` tool surface.
  - `graphify --mcp` — graphify itself can run as an MCP stdio server, which is an
    alternative to hand-writing `graphify_mcp_server.py` from scratch; worth evaluating
    during implementation.
  - `graph.json` schema: `{"nodes": [{"id","label","file_type","source_file",
    "source_location","_origin",...}], "links": [{"source","target","relation",
    "confidence","source_file","weight","_origin"}], "directed": bool}`.
- **System under test**: `stleary/JSON-java` cloned via `git clone --depth 1` into
  `sut/`. Confirmed: Maven project (`pom.xml`), 26 classes under `src/main/java/org/json`,
  792 unit tests, all passing out of the box.
- **JaCoCo wiring**: `org.jacoco:jacoco-maven-plugin:0.8.12` added to `sut/pom.xml`
  (`prepare-agent` + `report` bound to the `test` phase). Confirmed `mvn test` produces
  `sut/target/site/jacoco/jacoco.xml` (and `.csv`/`.html`) with per-class/method
  INSTRUCTION/LINE/BRANCH/COMPLEXITY/METHOD counters — this is the file our coverage
  parser reads.
- **Maven**: no system-wide Maven/`mvn` was available. Apache Maven 3.9.16 was
  downloaded and unzipped into `tools/apache-maven-3.9.16/` (no admin install needed).
  Run via `tools/apache-maven-3.9.16/bin/mvn.cmd` with `JAVA_HOME` set to the installed
  JDK 21 (`C:\Program Files\openjdk-21.0.2_windows-x64_bin\jdk-21.0.2`).
- **Java**: OpenJDK 21.0.10 already present and on PATH; used as-is.

## 11. Web UI (React Flow + FastAPI backend)

Added a browser-based UI on top of the existing CLI pipeline, per user
request, using React Flow for the knowledge-graph visualization.

### Architecture
- `ui_backend/` - FastAPI app (`api.py`) exposing read-only + action
  endpoints, all thin wrappers around existing modules (never
  reimplements logic):
  - `graph_service.py` - converts `graphify_mcp_server._load_graph()`
    output into React-Flow-shaped `{nodes, edges}` JSON, attaches
    per-class JaCoCo coverage %, computes a "god nodes + N-hop neighbors"
    default view (restricted to `src/main/java` whole-class nodes -
    raw-degree god nodes are dominated by test classes with many outgoing
    `calls` edges, which isn't a useful default to browse coverage
    against), and an `expand_subgraph()` op for click-to-expand.
  - `coverage_service.py` - wraps `maven_mcp_server.get_coverage_report()`
    and `reports/suite_health.json` (same data `view_coverage_deltas.py`
    reads).
  - `reports_service.py` - lists/reads `reports/qa_report_*.md`.
  - `state_service.py` - structured (JSON) equivalent of
    `demo_snapshot.py`'s printed checks.
  - `run_service.py` - runs `run_demo._run_pipeline` as an asyncio
    background task per request, forwarding its `progress_cb` events into
    a per-run `asyncio.Queue` that `GET /api/run/{id}/events` drains as a
    Server-Sent Events stream.
  - `reset_service.py` - calls `reset_demo_state.py`'s functions directly
    (not via subprocess), capturing their `print()` output via
    `contextlib.redirect_stdout` into a returned log string.
- `run_demo.py` was refactored (backward-compatibly) to accept an optional
  `progress_cb: Callable[[dict], None]` parameter threaded through
  `_run_pipeline`, emitting structured events (`setup_graph_start`,
  `planner_done`, `generator_result`, `post_generation_build_done`,
  `reviewer_done`, `pipeline_done`, etc.) at each existing `logger.info`
  call site. The CLI (`python run_demo.py ...`) is unaffected - it simply
  never passes `progress_cb`.
- `ui/` - Vite + React + TypeScript frontend. Key dependencies: `reactflow`
  (graph canvas), `dagre` (auto-layout, since React Flow has no built-in
  layout engine), `recharts` (coverage history line chart), `react-markdown`
  (report viewer). Four tabs (Run/Graph/Coverage/Reports) plus a header
  status strip (polls `/api/state` every 5s) and global Reset button.

### Real gotcha found during implementation
FastAPI route handlers that call `asyncio.get_event_loop()` fail with
`RuntimeError: There is no current event loop in thread 'AnyIO worker
thread'` when the route function is declared `def` (sync) - FastAPI runs
sync handlers in a worker thread pool with no event loop of their own.
Fixed by declaring `POST /api/run` as `async def` and using
`asyncio.get_running_loop()` (not the deprecated `get_event_loop()`) inside
`run_service.start_run()`.

### Verified working end-to-end
- All read-only endpoints (`/api/graph`, `/api/graph/expand`,
  `/api/graph/search`, `/api/coverage`, `/api/coverage/history`,
  `/api/coverage/delta`, `/api/reports`, `/api/state`) tested against real
  data from the repo's actual Graphify graph and JaCoCo reports.
- `POST /api/run` (spec mode, `--target-class=StringBuilderWriter`
  equivalent) exercised the full real pipeline through the FastAPI
  backend - Planner/Generator/Guardrails/compile-check/Reviewer all ran
  correctly, producing the same kind of genuine coverage increase
  (89.97% -> 90.1%) observed via the CLI.
- `POST /api/reset` verified to produce byte-for-byte the same reset
  behavior as `python reset_demo_state.py --baseline-build`.
- Frontend verified via `tsc -b` (zero type errors) and `npm run build`
  (production bundle builds cleanly, 929 KB minified/280 KB gzipped -
  acceptable for a demo tool, `reactflow`+`recharts`+`dagre` account for
  most of it).

### 11a. Run tab: embedded live Knowledge Graph + Agent Flow panels (follow-up)

Two further requests refined the Run tab after initial delivery:

1. **Embedded, live-updating knowledge-graph preview in the Run tab** (not
   just the separate Graph tab). Added:
   - `ui_backend/graph_service.get_view_for_class(class_name, depth)` +
     `GET /api/graph/by-class?class_name=...` - returns the subgraph for a
     named class using the *same* membership rule the Planner agent's
     `--target-class` override uses (`agents/planner_agent.py:_rank_targets`),
     so the preview shown corresponds exactly to what the pipeline will
     target.
   - `ui/src/graphLayout.ts` - shared dagre-layout/coloring logic extracted
     out of `GraphTab.tsx` so both the standalone Graph tab and the Run
     tab's embedded preview render identically; added a `NodeStatus`
     concept (`target`/`accepted`/`rejected`) so nodes can be highlighted
     live as SSE events arrive (blue outline = Planner-selected target,
     green = Generator accepted, red = rejected/compile-failed).
2. **Step-by-step Agent Flow diagram** (also React Flow, per request) as an
   alternative view in the same right-hand panel (toggle: "Agent Flow" /
   "Knowledge Graph"). Added `ui/src/agentFlow.ts`:
   - A static 8-node pipeline diagram (Graphify -> RAG -> Baseline Build ->
     Planner -> Generator+Guardrails -> Re-run Tests -> Reviewer -> Done),
     plus a dashed "iterate" loop-back edge from Reviewer to Planner.
   - `statusFromEvent()` maps every SSE event type already emitted by
     `run_demo.py`'s `progress_cb` (`setup_graph_start/done`,
     `setup_rag_start/done`, `baseline_build_start/done`,
     `iteration_start`, `planner_done`, `no_targets`, `generator_start`,
     `compile_check_start`, `post_generation_build_start/done`,
     `reviewer_start/done`, `pipeline_done`) to a per-step
     pending/active/done/error status, so the diagram advances live during
     a run with zero additional backend changes - it's a pure frontend
     reinterpretation of the same event stream the timeline text list
     already consumed.








