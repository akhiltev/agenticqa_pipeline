# The AI QA Engineer — Executive Demo Brief & Architecture

**Audience:** CEO / executive sponsor, customer side
**Purpose:** A self-contained narrative + architecture reference for presenting this
demo live. Read top-to-bottom for the story; use the architecture sections as
backup material for technical follow-up questions.

---

## 1. The One-Sentence Pitch

> **We built an AI teammate that writes, validates, and runs its own tests against
> your real codebase — and proves, with hard coverage numbers, that quality is
> improving every single time your engineers ship code.**

This isn't a chatbot that suggests test ideas. It is a closed-loop, autonomous
system: it reads your code, reads your requirements, writes real test code,
**checks its own work before anyone sees it**, compiles and runs that code
against your actual build tooling, measures the real coverage impact, and
produces a report a QA lead or engineering manager can act on immediately —
all without a human writing a single line of test code.

---

## 2. The Business Problem

Every engineering organization has the same three symptoms:

1. **Test coverage lags feature delivery.** Teams ship fast; tests get written
   "later," and later rarely comes.
2. **QA is a bottleneck, not a partner.** Manual test authoring doesn't scale
   with the pace of modern CI/CD, and hiring more QA engineers is slow and
   expensive.
3. **"We think coverage improved" vs. "we can prove it."** Leadership rarely
   gets a trustworthy, quantified answer to "is our test suite actually
   getting better, release over release?"

The AI QA Engineer directly answers all three: it authors tests continuously,
in the background, scoped to what actually changed, and produces auditable,
timestamped coverage evidence every time it runs.

---

## 3. The Demo Story (what you will see, in order)

The demo runs against a **real, non-trivial open-source Java codebase**
(`stleary/JSON-java` — a widely used JSON library, ~30-40 classes, real
production code, not a toy example) so nothing is staged or synthetic.

### Act 1 — "Show me the codebase's brain" (Knowledge Graph)
We open the **Graph** tab. Within seconds, the AI has built a structural map
of the *entire* codebase — every class, every method, every call relationship
— without ever running an LLM. This is **Graphify**, a deterministic,
AST-based knowledge graph engine. It's the AI's ground truth about what code
actually exists, so later on it can never invent a method that isn't real.
We click a class, its coverage-colored neighbors light up. This is the same
graph the AI uses internally to reason about the codebase — we're just making
it visible for the demo.

### Act 2 — "Give it a goal in plain English" (Run tab)
We type a feature requirement in plain English — e.g. *"bounds checking for
array offsets and null handling in string writers"* — pick a target area, and
click **Run**. This is exactly how a Product Owner or QA lead would kick off
work: no code, no tickets, just intent.

### Act 3 — "Watch it think, step by step" (live Agent Flow)
A live diagram lights up in real time, stage by stage:

1. **Graphify** rebuilds the knowledge graph (a few seconds).
2. **RAG** (retrieval-augmented generation) indexes the requirement text and
   any linked work items into a semantic search index.
3. **Baseline build** — runs the *real* Maven/JaCoCo build to get today's
   actual coverage numbers, before any AI-written code exists.
4. **Planner Agent** combines structural knowledge (from Graphify) with
   requirement semantics (from RAG) to propose specific, ranked test targets
   — not "test the JSON library," but "test `StringBuilderWriter.append()`
   because it has an unguarded null branch relevant to the stated
   requirement."
5. **Generator Agent** drafts real JUnit test code with an LLM (Azure OpenAI),
   then — critically — **checks its own work** (see Act 4) before anything
   touches disk.
6. **Re-run tests** — the real build runs again, now with the new AI-authored
   tests included.
7. **Reviewer Agent** compares before/after coverage, decides whether to loop
   back for another round or stop, and writes a human-readable report.
8. **Done.**

Every one of these is a real, running system component — not a canned
animation. If the baseline build fails, the diagram shows red. If a test is
rejected, the diagram shows it. Nothing is faked for the demo.

### Act 4 — "It doesn't trust itself blindly" (Guardrails)
This is the moment that earns executive trust. Before any AI-generated test is
allowed to touch the filesystem, it must pass five independent, automated
checks (**Guardrails AI**):

- Is the code even syntactically valid?
- Does it call **only classes and methods that Graphify confirmed actually
  exist** — i.e., zero tolerance for the AI hallucinating an API that doesn't
  exist in your code?
- Does it follow the team's test-naming conventions?
- Does it avoid unsafe operations (no shelling out, no unrestricted
  file/network access, no `System.exit`)?
- Is it using the correct test framework for *this specific* project (e.g.
  JUnit4 vs JUnit5), not a generic guess?

If a generated test fails any check, the AI **retries with the specific
failure reason fed back to it**, up to a bounded number of attempts — and if
it still can't produce something safe and correct, it skips that target and
says so honestly in the report, rather than silently writing broken code.
This bounded-retry, fail-safe design is what makes it safe to run unattended.

### Act 5 — "Prove it with numbers" (Coverage tab)
We open the **Coverage** tab: real JaCoCo instrumentation numbers, per-class,
with before/after deltas from this exact run, plus a run-history trend chart.
We can click through to the actual line-by-line, green/red-highlighted source
report — the same artifact a Java engineering team already trusts today. This
is not an AI's self-assessment; it's the industry-standard Java coverage
tool, running against the AI's own output.

### Act 6 — "It reads the report so you don't have to" (Reports tab)
A Markdown QA report is generated automatically: what was tested, why, the
exact coverage delta, and a full accounting of anything rejected and why. In
PR mode, this same summary is posted as a comment directly on the pull
request — meeting engineers where they already work.

### Act 7 — "It plugs into what you already use" (Continuous mode)
The same pipeline can be pointed at a real pull request, scoped to just the
diff, and triggered automatically as part of CI — or run in "continuous"
mode, sweeping every open PR. The demo's PR/requirements integrations are
pluggable; **Azure DevOps (Boards + Repos)** are wired end-to-end with real
credentials as the reference integration, and the same interface is ready for
Jira and GitHub with no redesign — just implement one small adapter per
system.

---

## 4. Why This Matters to the Business (translate the tech into outcomes)

| What you saw | What it means for the business |
|---|---|
| Knowledge graph built in seconds, zero LLM cost | Structural understanding of even large codebases is fast and cheap — this scales to real enterprise repos, not just demo-sized ones. |
| Plain-English requirement → ranked test targets | QA effort is *directed*, not random — it tests what matters to the current release, not everything indiscriminately. |
| Guardrails reject hallucinated/unsafe code before it's ever written | The AI is **safe to run unattended** in a real CI pipeline. This is the difference between "AI demo" and "AI in production." |
| Real Maven/JaCoCo execution, not simulated | Every coverage number shown is independently verifiable by your own engineers with tools they already trust. |
| Bounded iteration loop with a hard budget | The system always terminates predictably — no runaway costs, no infinite loops, demo-safe and production-safe. |
| Cross-run coverage ledger | Leadership gets a trend line, not a snapshot — "is quality improving" becomes a graph, not an opinion. |
| PR-scoped mode + PR comment posting | Fits into the engineering workflow you already have (Azure DevOps today; Jira/GitHub are a small, pre-designed step away). |

**Bottom line:** this reduces the QA authoring bottleneck, gives leadership an
auditable, numeric answer to "is our test suite getting better," and does it
in a way that is architecturally safe to trust in a real pipeline — not a
one-off prototype.

---

## 5. System Architecture

### 5.1 High-level component map

```
                         ┌──────────────────────────────────────────────────┐
                         │                  Web UI (React)                  │
                         │  Run · Graph · Coverage · Reports  (localhost)   │
                         └───────────────────────┬──────────────────────────┘
                                                  │ REST + Server-Sent Events
                         ┌───────────────────────▼──────────────────────────┐
                         │        UI Backend (FastAPI, ui_backend/)         │
                         │   run orchestration · graph API · coverage API   │
                         └───────────────────────┬──────────────────────────┘
                                                  │ drives
                         ┌───────────────────────▼──────────────────────────┐
                         │      Orchestrator (run_demo.py, single script)   │
                         │  spec | pr | continuous mode entrypoint          │
                         └──┬───────────┬───────────┬───────────┬──────────┘
                            │ A2A       │ A2A        │ A2A       │ MCP tools
                     ┌──────▼───┐ ┌─────▼─────┐ ┌────▼──────┐   │
                     │ Planner  │ │ Generator │ │ Reviewer  │   │
                     │  Agent   │ │  Agent    │ │  Agent    │   │
                     └────┬─────┘ └─────┬─────┘ └───────────┘   │
                          │             │  Guardrails AI          │
                          │             │  (5 validators)          │
              ┌───────────▼───┐   ┌─────▼──────────────┐   ┌──────▼──────────┐
              │  Graphify KG   │   │   RAG / Chroma      │   │  Maven + JaCoCo │
              │ (AST-based,    │   │  (requirement       │   │  (real build,   │
              │  no LLM)       │   │   embeddings)        │   │   coverage)     │
              └───────┬────────┘   └─────────┬───────────┘   └────────┬────────┘
                      │                       │                       │
              ┌───────▼───────────────────────▼───────────────────────▼────────┐
              │           System Under Test (SUT): real Java codebase          │
              │              (stleary/JSON-java, Maven project)                │
              └──────────────────────────────────────────────────────────────┘

        External integrations (pluggable, config-driven):
        Requirements: mock fixtures | Azure Boards (real, wired) | Jira (stub)
        PR host:      mock fixtures | Azure Repos (real, wired)  | GitHub (stub)
        LLM:          Azure OpenAI (all agent reasoning + code generation)
```

### 5.2 Component-by-component

**Orchestrator (`run_demo.py`)**
Single Python entrypoint that drives the full pipeline end-to-end. Supports
three modes:
- `--mode=spec` — full-suite planning from static requirement specs.
- `--mode=pr --pr=<id>` — scoped to a single pull request's diff + linked
  requirement.
- `--mode=continuous` — sweeps every open PR from the configured PR
  connector, applying the PR-scoped flow to each (this is what would run on a
  schedule / webhook in production).

**Knowledge Graph — Graphify**
Deterministic, AST-based static analysis of the Java codebase — no LLM
involved, so it's fast, cheap, and 100% reproducible. Produces a graph of
classes, methods, and call/dependency edges. This graph is the single source
of truth the Generator's guardrails use to reject any AI-written test that
references a class or method that doesn't actually exist in the codebase —
this is the core anti-hallucination mechanism.

**Requirements Ingestion — RAG (Retrieval-Augmented Generation)**
Requirement text (from a requirements tracker or free-text input) is chunked,
embedded, and indexed into a local vector store (**Chroma**) so the Planner
Agent can semantically retrieve the requirement content most relevant to a
given code target, grounding test intent in actual acceptance criteria rather
than guessing.

**Multi-Agent Layer — Google A2A (Agent2Agent) protocol**
Three independent agents, each its own HTTP service, communicating over the
open **A2A protocol** (the same interoperability standard designed for
cross-vendor agent communication) — not a single monolithic prompt:
- **Planner Agent** — ranks test targets using graph structure + RAG context.
- **Generator Agent** — drafts JUnit test code via Azure OpenAI, enforces
  Guardrails AI, retries on failure with corrective feedback.
- **Reviewer Agent** — evaluates coverage deltas, decides continue/stop,
  writes the QA report and PR comment.

Using a standard protocol (rather than a bespoke integration) means these
agents — or a customer's own agents — can be swapped, scaled independently,
or reused across other automation workflows without redesigning the
integration.

**Tool Access — MCP (Model Context Protocol)**
Agents access the knowledge graph and the Maven/JaCoCo build tooling through
standardized MCP tool servers, rather than ad hoc integration code. This
means the *same* tool servers are usable by any MCP-compatible agent or
client outside this specific demo (e.g. an IDE assistant, a different
orchestrator) with zero code changes.

**Guardrails AI — the safety layer**
Every piece of AI-generated test code passes through five automated checks
before it is written to disk or executed:
1. Syntax sanity (balanced braces/parens; a full compiler check follows before
   the code is ever run against the real test suite).
2. **No hallucinated APIs** — every referenced class/method is cross-checked
   against the Graphify graph.
3. Naming convention compliance.
4. No unsafe side effects (process spawning, unrestricted network/file I/O,
   `System.exit`).
5. Correct test framework for *this* project (e.g. rejects JUnit5 syntax on a
   project pinned to JUnit4 — a real, project-specific compile-hallucination
   class Guardrails AI catches that a naive check would miss).

On failure, bounded retries with the specific error fed back to the LLM;
after the retry budget is exhausted, the target is skipped and logged — never
silently broken code.

**Execution & Coverage — Maven + JaCoCo**
Real `mvn test` runs, instrumented with JaCoCo, against the actual codebase.
This is the same tool a human QA/dev team already uses and trusts — the AI
doesn't get to grade its own homework with a synthetic metric.

**Reporting & Continuous Improvement**
- Human-readable Markdown QA report per run (targets tested, coverage deltas,
  guardrail rejections, pass/fail).
- PR-comment-style summary posted automatically in PR mode.
- Cross-run ledger (`suite_health.json`) tracking coverage over time — the
  data source for the trend chart shown in the Coverage tab.

**Pluggable Integrations**
Requirements and PR sources are selected purely by configuration
(`REQUIREMENTS_SOURCE`, `PR_SOURCE`), with no code changes required:

| Integration | Status |
|---|---|
| Mock fixtures (requirements + PRs) | Fully working, default, zero credentials required |
| Azure Boards (requirements) | **Fully wired, real REST API, real PAT auth** |
| Azure Repos (PRs) | **Fully wired, real REST API, real PAT auth, posts real PR comments** |
| Jira Cloud | Interface defined, stubbed — clear implementation path, no redesign needed |
| GitHub | Interface defined, stubbed — clear implementation path, no redesign needed |

**Demo UI (`ui/` + `ui_backend/`)**
A React front end + FastAPI backend that makes every part of the above
visible and interactive for a live audience: trigger runs, watch the agent
flow in real time via Server-Sent Events, explore the knowledge graph,
inspect JaCoCo coverage (including the authoritative line-by-line HTML
report), and browse historical QA reports — a thin, honest window onto the
same CLI-drivable pipeline underneath (nothing in the UI is a special demo
path; every button calls the identical code path available from the command
line).

### 5.3 Design guarantees worth calling out to a technical follow-up audience

- **Bounded execution.** Both the plan→generate→review loop (max iterations)
  and guardrail retries (max retries) are capped by configuration — the
  system always terminates predictably. No runaway LLM costs, no infinite
  loops.
- **Deterministic structural ground truth.** The knowledge graph (Graphify)
  is AST-based, not LLM-based — it's exact and reproducible, and it's what
  makes the anti-hallucination guardrail possible at all.
- **Secrets hygiene.** All credentials (Azure OpenAI key, Azure DevOps PAT)
  are environment-variable only, never committed; nothing here requires
  checking secrets into source control.
- **Offline-capable core.** Aside from the LLM calls themselves, the entire
  pipeline can run without external network access (mock connectors, local
  Chroma vector store, local Maven build) — useful for air-gapped or
  regulated environments.
- **Every demo artifact is a real artifact.** The coverage numbers come from
  real JaCoCo XML. The knowledge graph comes from real AST parsing. The test
  code is real, compilable Java. Nothing shown in the demo is mocked *for the
  purpose of the demo* — the only mocking is in the requirements/PR data
  source, which is a deliberate, swappable choice to avoid needing live
  customer credentials on stage.

---

## 6. Suggested Executive Talking Points / Closing

- *"This isn't 'AI writes some tests.' This is a closed-loop system with a
  built-in referee — it checks its own honesty against your actual code
  before anything runs, and it proves its impact with the same coverage tool
  your engineers already trust."*
- *"It's built on open, vendor-neutral protocols — A2A for agent
  communication, MCP for tool access — so this isn't a black box you're
  locked into; it's a pattern your own teams can extend."*
- *"The two real, credentialed integrations you're seeing today (Azure Boards
  and Azure Repos) are the *reference implementation* — the same pattern
  plugs into Jira, GitHub, or your internal systems with a small, well-scoped
  engineering task, not a rebuild."*
- *"The output isn't a demo screenshot — it's a Markdown report and a
  coverage trend line your QA lead could act on this afternoon."*

---

*Prepared as supporting material for a live product demonstration. Technical
detail sourced from the project's `REQUIREMENTS.md` and current
implementation; see that document for the full functional/non-functional
requirements spec.*



