# Agentic QA Pipeline — Demo

An "AI QA Engineer" multi-agent pipeline: given a feature spec / requirements
source and a real Java codebase, it plans test targets, generates JUnit
tests, validates them with Guardrails AI, executes them with Maven + JaCoCo,
measures coverage, iterates, and produces a human-readable QA report.

See [REQUIREMENTS.md](REQUIREMENTS.md) for the full requirements spec and
architecture decisions. This README covers setup and how to run the demo.

## Web UI (React Flow graph + coverage dashboard + live run trigger)

A browser-based UI (`ui/` + `ui_backend/`) sits on top of everything below -
visualize the Graphify knowledge graph interactively, browse JaCoCo
coverage and run history, trigger `run_demo.py` pipeline runs and watch
their progress live, browse QA reports, and reset the demo state, all
without touching a terminal (though the CLI paths documented later in this
README still work exactly the same and are what the UI calls under the
hood).

### One-time setup

```powershell
# Python backend deps (adds fastapi to the existing venv)
.\.venv\Scripts\pip install -r requirements.txt

# Frontend deps
cd ui
npm install
cd ..
```

### Running (two terminals, for the demo)

```powershell
# Terminal 1: UI backend (FastAPI + SSE), port 8090
.\.venv\Scripts\python.exe -m uvicorn ui_backend.api:app --port 8090

# Terminal 2: frontend dev server, port 5173
cd ui
npm run dev
```
Open http://localhost:5173 in a browser. Tabs: **Run** (trigger a pipeline
run with a live event timeline, plus an embedded React Flow panel toggling
between an **Agent Flow** diagram - Graphify -> RAG -> Baseline Build ->
Planner -> Generator+Guardrails -> Re-run Tests -> Reviewer, each step
lighting up live as it happens - and a **Knowledge Graph** preview scoped
to the current target class, with nodes highlighted blue/green/red as
Planner/Generator events arrive), **Graph** (React Flow view of the full
Graphify knowledge graph, default = god nodes + neighbors, click to expand,
search box, node color = coverage %, plus a toggleable **Graphify Toolkit**
side panel exposing the full CLI toolkit as buttons: `update --no-cluster`
(fast AST rebuild), `cluster-only` (full clustering + regenerates
`GRAPH_REPORT.md` + `graph.html`, viewable in-panel/in a new tab), and the
read-only query commands `god-nodes --top`, `explain "<name>"`,
`path "<a>" "<b>"`, `affected "<name>"`, and `query "<question>"` - each
runs the exact same `graphify` executable the CLI workflow below uses, via
`/api/graphify/*` endpoints on the UI backend), **Coverage** (an "Open full
JaCoCo report ↗" button that opens the real, authoritative
`sut/target/site/jacoco/index.html` report - now served directly by the UI
backend at `/api/jacoco/html/*` - plus summary gauges, a searchable/sortable
per-class table with inline coverage bars and per-run delta column, a
run-history chart, and a per-row "view ↗" button that opens that exact
class's own JaCoCo HTML page with line-by-line green/red source
highlighting), **Reports** (browse `qa_report_*.md`). The
header shows a live status strip and a global **Reset Demo State** button
(wraps `reset_demo_state.py`, same as the CLI).

### Production-style single-process run (optional)

```powershell
cd ui
npm run build
cd ..
# Serve ui/dist as static files behind the same FastAPI app, e.g. by adding
# app.mount("/", StaticFiles(directory="ui/dist", html=True)) to
# ui_backend/api.py - not wired by default since the two-terminal dev setup
# is simpler to iterate on and was the option chosen for this demo.
```

## Demo Day: Before/After Workflow

If you're demoing this live, use `reset_demo_state.py` beforehand to get a
clean, honest "before" state, then `demo_snapshot.py` to narrate the
before/after story around a `run_demo.py` run.


```powershell
# 1. Right before the demo: reset to a clean baseline (also rebuilds a
#    fresh JaCoCo report with ZERO AI-generated tests, so you have a real
#    "before" coverage number to show).
.\.venv\Scripts\python.exe reset_demo_state.py --baseline-build

# 2. Show the "before" state to your audience:
.\.venv\Scripts\python.exe demo_snapshot.py
#    -> no AI-generated tests, baseline coverage %, no reports, no RAG
#       index, no knowledge graph yet.
start sut\target\site\jacoco\index.html   # optional: show the "before" JaCoCo report

# 3. Run the pipeline live (talks to real Azure OpenAI, real A2A agents,
#    real Guardrails AI validation, real mvn test + JaCoCo):
.\.venv\Scripts\python.exe run_demo.py --mode=spec --target-class=StringBuilderWriter --question="write char array offset length bounds checking IndexOutOfBoundsException and append CharSequence null handling"

# 4. Show the "after" state:
.\.venv\Scripts\python.exe demo_snapshot.py
#    -> lists the newly-generated test file(s), updated coverage %, the new
#       QA report, and confirms the RAG index + knowledge graph were built.
start sut\target\site\jacoco\index.html                          # refreshed JaCoCo report
notepad (Get-ChildItem reports\qa_report_*.md | Select-Object -Last 1).FullName
.\.venv\Scripts\python.exe view_coverage_deltas.py                # explicit before/after delta

# 5. (Optional) run again immediately to show the loop is idempotent /
#    the suite keeps improving, or reset and re-run for a second take.
.\.venv\Scripts\python.exe reset_demo_state.py --baseline-build
```

**Why a reset script instead of just re-running?** Without resetting,
`reports/`, `rag/chroma_store/`, and `sut/graphify-out/` accumulate across
every run you've ever done (including our own validation runs while
building this demo), so a live re-run wouldn't show a clean before/after -
`reset_demo_state.py` clears all of that while leaving `sut/pom.xml`'s
JaCoCo plugin addition untouched (it's a permanent part of the demo setup,
not generated content) and never touches your `.env` configuration.

**Why `--target-class`?** Without real embeddings deployed on Azure (RAG
retrieval falls back to an offline, non-semantic hash embedding - see
REQUIREMENTS.md section 6a), the Planner's ranking heuristic tends to
re-select high-fan-in "god nodes" (e.g. `CDL`) regardless of the actual
`--question` asked, and `CDL` happens to have a known, real, pre-existing
bug (trailing blank lines aren't skipped) that makes every generated test
against it fail at runtime - a "build failed" outcome rather than a clean
coverage increase. `--target-class=StringBuilderWriter` deterministically
points the Planner at a simpler, well-behaved class with genuinely
uncovered lines, reliably producing a clean, coverage-increasing "after"
state for a demo. Omit it (and just use `--question`) to show the
"an AI agent found and proved a real bug" story instead - both are
legitimate, real outcomes of this pipeline.

## Architecture at a glance

```
requirements (Azure Boards | Jira-stub | mock)  ──┐
specs/*.md                                        ├──► RAG (Chroma) ──┐
                                                    │                  │
sut/ (JSON-java)  ──► Graphify (AST graph) ────────┴──────────────────┤
                                                                       ▼
                                              ┌─────────────┐   A2A   ┌──────────────┐
PR (Azure Repos | GitHub-stub | mock) ───────►│ Orchestrator│◄───────►│ Planner Agent │
                                               │ (run_demo.py)│        └──────────────┘
                                               └──────┬──────┘   A2A   ┌──────────────┐
                                                      ├───────────────►│ Generator     │
                                                      │                │ Agent +       │
                                                      │                │ Guardrails AI │
                                                      │                └──────────────┘
                                                      │         MCP    ┌──────────────┐
                                                      ├───────────────►│ Maven/JaCoCo  │
                                                      │                │ MCP tools     │
                                                      │  A2A           └──────────────┘
                                                      └───────────────►┌──────────────┐
                                                                        │ Reviewer     │
                                                                        │ Agent        │
                                                                        └──────────────┘
```

- **A2A** (`agents/`): Orchestrator, Planner, Generator, Reviewer talk over
  real A2A (JSON-RPC over HTTP) using the `a2a-sdk` package.
- **MCP** (`mcp_servers/`): Graphify + Maven/JaCoCo are exposed as MCP tools
  (`mcp` package, `MCPServer`). They're independently runnable as real stdio
  MCP servers; the Orchestrator also calls their functions in-process for
  reliability in this demo.
- **Graphify**: deterministic AST knowledge graph of the SUT
  (`sut/graphify-out/graph.json`), queried for structural test-target ranking
  and for the Generator's hallucination guardrail.
- **RAG**: Chroma vector store (`rag/chroma_store/`) over normalized
  requirement items + `specs/*.md`.
- **Guardrails AI** (`qa_guardrails/`): validates generated JUnit code before
  it's ever written to disk or executed.
- **JaCoCo**: wired into `sut/pom.xml`, parsed by `mcp_servers/maven_mcp_server.py`.

## Prerequisites

- Python 3.12 (a project venv is expected at `.venv/`)
- Java 21 (`JAVA_HOME` set) — see `config/settings.py` / `.env`
- Apache Maven — a local copy is expected at `tools/apache-maven-3.9.16/`
  (downloaded during setup; not required on system PATH)
- (Optional) Azure OpenAI deployment for live LLM calls
- (Optional) Azure DevOps PAT for real Azure Boards/Azure Repos connectors

## Setup

```powershell
# 1. Create & populate the venv (already done in this repo checkout)
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# 2. Configure environment
copy .env.example .env
# edit .env: fill in AZURE_OPENAI_* to enable live generation; leave
# REQUIREMENTS_SOURCE=mock / PR_SOURCE=mock for the credential-free demo.

# 3. System under test is already cloned at sut/ (stleary/JSON-java) with
#    JaCoCo wired into its pom.xml. To re-clone from scratch:
git clone --depth 1 https://github.com/stleary/JSON-java.git sut
```

## Validating Azure OpenAI settings

```powershell
.\.venv\Scripts\python.exe validate_azure_openai.py
```
Prints your loaded config (API key masked) and makes real chat + embeddings
calls, reporting PASS/FAIL with the raw error for each so misconfiguration
(wrong endpoint, stale key, missing deployment) is easy to diagnose. See
REQUIREMENTS.md section 6a for real gotchas found while validating this
demo's own Azure OpenAI resource (e.g. Azure AI Foundry endpoints use a
different client construction than classic `*.openai.azure.com` resources).

## Viewing JaCoCo coverage, coverage deltas, and Graphify notes

**JaCoCo HTML report** (browsable line/branch coverage per class):
```powershell
start sut\target\site\jacoco\index.html
```
Also available: `sut/target/site/jacoco/jacoco.csv` (raw per-class numbers)
and `jacoco.xml` (what `mcp_servers/maven_mcp_server.get_coverage_report()`
parses).

**Coverage deltas across pipeline runs** (reads `reports/suite_health.json`):
```powershell
.\.venv\Scripts\python.exe view_coverage_deltas.py            # last 2 runs + delta
.\.venv\Scripts\python.exe view_coverage_deltas.py --n 5       # last 5 runs + delta between the 2 most recent
.\.venv\Scripts\python.exe view_coverage_deltas.py --all       # full run history summary (no delta)
```
Also useful directly: `reports/qa_report_<timestamp>.md` (one per run, with a
"Build Failed After Generation" section when a generated test correctly
catches a real bug) and `reports/suite_health.json` (raw ledger).

**Graphify notes** (architectural summary + interactive graph):
```powershell
# Community detection + human-readable report + interactive HTML graph.
# Placeholder "Community N" labels unless an LLM backend (GOOGLE_API_KEY etc.) is set.
cd sut
..\.venv\Scripts\graphify.exe cluster-only .
cd ..
start sut\graphify-out\GRAPH_REPORT.md   # god nodes, surprising connections, communities
start sut\graphify-out\graph.html        # interactive, clickable graph

# Quick CLI queries without full clustering:
.\.venv\Scripts\graphify.exe god-nodes --graph sut\graphify-out\graph.json --top 10
.\.venv\Scripts\graphify.exe explain "CDL" --graph sut\graphify-out\graph.json
.\.venv\Scripts\graphify.exe path "CDL" "JSONException" --graph sut\graphify-out\graph.json
```

## Running the demo

```powershell
# Spec-driven, full-suite mode (FR-24)
.\.venv\Scripts\python.exe run_demo.py --mode=spec --question="trailing blank lines in CSV parsing"

# Spec-driven mode with a deterministic target override (reliable for demos -
# see "Why --target-class?" above)
.\.venv\Scripts\python.exe run_demo.py --mode=spec --target-class=StringBuilderWriter --question="write char array offset length bounds checking IndexOutOfBoundsException and append CharSequence null handling"

# PR-scoped mode using the mock PR fixture (FR-25)
.\.venv\Scripts\python.exe run_demo.py --mode=pr --pr=PR-501

# Continuous mode: iterates over all "open" PRs from the PR connector (FR-26)
.\.venv\Scripts\python.exe run_demo.py --mode=continuous
```

Each run:
1. Rebuilds the Graphify knowledge graph (`graphify update`, AST-only, no LLM).
2. Indexes mock/real requirement items + `specs/*.md` into Chroma.
3. Runs the Maven/JaCoCo baseline (`mvn test`).
4. Loops: Planner (A2A) → Generator (A2A, Azure OpenAI + Guardrails AI) →
   write accepted tests → re-run `mvn test` → Reviewer (A2A) decides
   continue/stop.
5. Writes `reports/qa_report_<timestamp>.md` and appends to
   `reports/suite_health.json`.

**Without Azure OpenAI configured**, steps 1–3 and the Planner/Reviewer legs
still run fully live; the Generator will report `status: "rejected"` with a
clear "Azure OpenAI is not configured" error instead of crashing — this
validates the entire pipeline's plumbing offline (NFR-1).

## Switching connectors to real Azure DevOps

Set in `.env`:
```
REQUIREMENTS_SOURCE=azure_boards
PR_SOURCE=azure_repos
AZURE_DEVOPS_PAT=...
AZURE_DEVOPS_ORG=...
AZURE_DEVOPS_PROJECT=...
AZURE_DEVOPS_REPO=...
```
No code changes required (NFR-3). Jira and GitHub connectors are documented
stubs (`connectors/requirements/jira_connector.py`,
`connectors/prs/github_connector.py`) for future follow-up (NFR-4).

## Repository layout

See REQUIREMENTS.md section 7 for the full intended layout; the
implemented layout follows it closely, with one deviation: the guardrails
package is named `qa_guardrails/` (not `guardrails/`) to avoid shadowing the
installed `guardrails-ai` PyPI package on `sys.path`.

## Running components standalone

```powershell
# Graphify MCP server (stdio)
.\.venv\Scripts\python.exe mcp_servers\graphify_mcp_server.py

# Maven/JaCoCo MCP server (stdio)
.\.venv\Scripts\python.exe mcp_servers\maven_mcp_server.py

# Any single A2A agent (for manual testing via curl/A2A client)
.\.venv\Scripts\python.exe agents\planner_agent.py
```

## Full Command Reference

All commands below assume you're in the project root (`d:\agentic_qa_pipeline`)
in a PowerShell prompt, unless noted otherwise.

### Environment setup

```powershell
# Create the venv (Python 3.12 recommended)
python -m venv .venv

# Install all dependencies
.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

# Configure environment variables
copy .env.example .env
notepad .env

# Clone the system under test (if not already present)
git clone --depth 1 https://github.com/stleary/JSON-java.git sut

# Download Apache Maven locally (if not already present)
Invoke-WebRequest -Uri "https://dlcdn.apache.org/maven/maven-3/3.9.16/binaries/apache-maven-3.9.16-bin.zip" -OutFile tools\maven.zip
Expand-Archive -Path tools\maven.zip -DestinationPath tools -Force
Remove-Item tools\maven.zip
```

### Validating configuration

```powershell
# Validate Azure OpenAI settings (chat + embeddings, masks the API key)
.\.venv\Scripts\python.exe validate_azure_openai.py

# Sanity-check every Python module compiles
.\.venv\Scripts\python.exe -m py_compile run_demo.py validate_azure_openai.py view_coverage_deltas.py `
    config\settings.py agents\generator_agent.py agents\reviewer_agent.py agents\a2a_client.py `
    agents\a2a_common.py agents\planner_agent.py mcp_servers\graphify_mcp_server.py `
    mcp_servers\maven_mcp_server.py qa_guardrails\test_code_guard.py rag\index_specs.py
```

### Running the demo pipeline

```powershell
# Spec-driven mode (FR-24)
.\.venv\Scripts\python.exe run_demo.py --mode=spec --question="trailing blank lines in CSV parsing"

# Spec-driven mode with a deterministic target override (reliable for demos)
.\.venv\Scripts\python.exe run_demo.py --mode=spec --target-class=StringBuilderWriter --question="write char array offset length bounds checking IndexOutOfBoundsException and append CharSequence null handling"

# PR-scoped mode using the mock PR fixture (FR-25)
.\.venv\Scripts\python.exe run_demo.py --mode=pr --pr=PR-501

# Continuous mode: iterates over all "open" PRs from the PR connector (FR-26)
.\.venv\Scripts\python.exe run_demo.py --mode=continuous
```

### Viewing results

```powershell
# JaCoCo HTML coverage report
start sut\target\site\jacoco\index.html

# Latest QA report (list them, then open the newest)
Get-ChildItem reports\qa_report_*.md | Sort-Object LastWriteTime | Select-Object -Last 1
notepad (Get-ChildItem reports\qa_report_*.md | Sort-Object LastWriteTime | Select-Object -Last 1).FullName

# Coverage deltas across runs
.\.venv\Scripts\python.exe view_coverage_deltas.py            # last 2 runs + delta
.\.venv\Scripts\python.exe view_coverage_deltas.py --n 5       # last 5 runs + delta between the 2 most recent
.\.venv\Scripts\python.exe view_coverage_deltas.py --all       # full run history summary (no delta)
```

### Graphify: rebuilding and exploring the knowledge graph

```powershell
# AST-only rebuild (no LLM, fast) - what run_demo.py does automatically
cd sut
..\.venv\Scripts\graphify.exe update . --no-cluster
cd ..

# Full clustering + human-readable report + interactive HTML graph
cd sut
..\.venv\Scripts\graphify.exe cluster-only .
cd ..
start sut\graphify-out\GRAPH_REPORT.md
start sut\graphify-out\graph.html

# Quick CLI queries against the existing graph.json (no rebuild needed)
.\.venv\Scripts\graphify.exe god-nodes --graph sut\graphify-out\graph.json --top 10
.\.venv\Scripts\graphify.exe explain "CDL" --graph sut\graphify-out\graph.json
.\.venv\Scripts\graphify.exe path "CDL" "JSONException" --graph sut\graphify-out\graph.json
.\.venv\Scripts\graphify.exe affected "CDL" --graph sut\graphify-out\graph.json
.\.venv\Scripts\graphify.exe query "how does CDL relate to JSONException?" --graph sut\graphify-out\graph.json
```

### Running Maven / JaCoCo directly against the SUT

```powershell
cd sut
$env:JAVA_HOME = "C:\Program Files\openjdk-21.0.2_windows-x64_bin\jdk-21.0.2"   # adjust to your JDK path
..\tools\apache-maven-3.9.16\bin\mvn.cmd -version
..\tools\apache-maven-3.9.16\bin\mvn.cmd test -B
cd ..
```

### Running individual pipeline components standalone

```powershell
# Graphify MCP server (stdio transport, for real MCP clients)
.\.venv\Scripts\python.exe mcp_servers\graphify_mcp_server.py

# Maven/JaCoCo MCP server (stdio transport)
.\.venv\Scripts\python.exe mcp_servers\maven_mcp_server.py

# Individual A2A agents (each starts its own HTTP server)
.\.venv\Scripts\python.exe agents\planner_agent.py     # port 8801
.\.venv\Scripts\python.exe agents\generator_agent.py   # port 8802
.\.venv\Scripts\python.exe agents\reviewer_agent.py     # port 8803
```

### Maintenance / cleanup

```powershell
# Reset the RAG vector store (required after switching embedding backends,
# e.g. toggling AZURE_OPENAI_* configured/unconfigured - Chroma treats the
# embedding function as immutable per-collection metadata)
Remove-Item -Recurse -Force rag\chroma_store

# Restore the SUT + reports/RAG/graph to a clean "before" demo state.
# Prefer this over raw `git checkout -- .` in sut/ - that would also revert
# sut/pom.xml's intentional, permanent JaCoCo plugin addition (a real bug
# we hit once - see REQUIREMENTS.md section 6a).
.\.venv\Scripts\python.exe reset_demo_state.py --baseline-build

# Or just check current state without resetting anything:
.\.venv\Scripts\python.exe demo_snapshot.py
```


