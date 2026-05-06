# Graft — Core Agent PRD
**Version:** 0.1  
**Stack:** Python / uv / LangGraph / FastAPI / PyTorch  
**LLM Backend:** OpenAI-compatible spec (default: Claude via proxy, target: fine-tuned Qwen3-Coder)

## 1. Problem Statement

Existing dependency automation tools such as Dependabot and Renovate update lockfiles and manifests, but they do not modify application code. When a dependency introduces a breaking change such as a renamed API, removed function, signature change, or altered async contract, the upgrade can break the application and requires manual repair.

**Graft** is an autonomous agent that:
- Detects when a dependency has a new version
- Understands what changed in that dependency at the code level
- Determines whether those changes affect the specific codebase
- Writes or adapts tests to cover affected surfaces
- Fixes the application code
- Runs tests in an isolated sandbox until they pass
- Opens a pull request with a structured audit trail

The agent is a standalone Python module. A FastAPI layer exposes it over HTTP. The agent also records trajectories in a format suitable for supervised fine-tuning, GRPO, and reinforcement-learning-style experimentation with Qwen3-Coder.

## 2. Scope

### In scope (v1)
- Python ecosystem only (`pip` / `uv`, PyPI)
- GitHub repositories
- Projects using `pyproject.toml` or `requirements.txt`
- Agent-generated tests when affected symbols lack sufficient coverage
- Pull request creation with manual human review and merge

### Out of scope (v1)
- npm, Cargo, Maven, Go modules
- Auto-merge
- Multi-tenant SaaS billing, auth, and account management
- Frontend dashboard
- Broad polyglot repo support in v1

## 3. Agent Architecture

### 3.1 Mental Model

The agent is a closed-loop **Automated Program Repair (APR)** system.

```text
Reader → Planner → TestAuditor → Coder ⟲ (until tests pass or max retries)
                                    ↓
                                 PRWriter
```

Each node is a pure function that takes `GraftState` and returns a partial state update. The sandbox is the only execution boundary for external side effects such as test runs.

### 3.2 State Schema

```python
# agent/state.py
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages

class DepUsage(TypedDict):
    file: str
    line: int
    symbol: str           # e.g. "httpx.AsyncClient.get"
    context: str          # 5-line window around the call site
    test_coverage: bool   # does any existing test exercise this call site?

class MigrationStep(TypedDict):
    id: str
    type: Literal["rename", "signature_change", "semantic", "removal", "async_change"]
    old_symbol: str
    new_symbol: str | None
    affected_files: list[str]
    deterministic: bool
    notes: str

class TestSpec(TypedDict):
    file: str
    target_symbol: str
    test_code: str
    is_new: bool

class SandboxResult(TypedDict):
    passed: bool
    total: int
    failed_names: list[str]
    errors: list[str]
    stdout: str
    duration_ms: int

class StepTrace(TypedDict):
    attempt: int
    diff: dict[str, str]
    test_results: SandboxResult
    reward: float | None

class GraftState(TypedDict):
    job_id: str
    repo_path: str
    dep_name: str
    old_version: str
    new_version: str

    call_graph: list[DepUsage]
    dep_diff: str
    migration_guide: str

    migration_plan: list[MigrationStep]
    breaking_change_count: int
    affected_file_count: int
    confidence_score: float | None
    low_confidence: bool | None

    test_specs: list[TestSpec]
    baseline_result: SandboxResult
    test_results_current: SandboxResult

    current_diff: dict[str, str]
    attempt_traces: list[StepTrace]
    retry_count: int

    status: Literal["pending", "running", "success", "failed", "escalate"]
    pr_body: str | None
    pr_url: str | None

    messages: Annotated[list, add_messages]
```

### 3.3 Graph Definition

```python
# agent/graph.py
from langgraph.graph import StateGraph, END
from .state import GraftState
from .nodes import reader, planner, test_auditor, coder, pr_writer

MAX_RETRIES = 5

def route_after_coder(state: GraftState) -> str:
    if state["test_results_current"]["passed"]:
        return "pr_writer"
    if state["retry_count"] >= MAX_RETRIES:
        return "escalate"
    return "coder"

def escalate_node(state: GraftState):
    return {"status": "escalate"}

def build_graph(checkpointer):
    g = StateGraph(GraftState)

    g.add_node("reader", reader.run)
    g.add_node("planner", planner.run)
    g.add_node("test_auditor", test_auditor.run)
    g.add_node("coder", coder.run)
    g.add_node("pr_writer", pr_writer.run)
    g.add_node("escalate", escalate_node)

    g.set_entry_point("reader")
    g.add_edge("reader", "planner")
    g.add_edge("planner", "test_auditor")
    g.add_edge("test_auditor", "coder")

    g.add_conditional_edges("coder", route_after_coder, {
        "coder": "coder",
        "pr_writer": "pr_writer",
        "escalate": "escalate",
    })

    g.add_edge("pr_writer", END)
    g.add_edge("escalate", END)
    return g.compile(checkpointer=checkpointer)
```

## 4. Node Specifications

### 4.1 Reader Node — Deterministic, No LLM

**Purpose:** Build the dependency usage map and gather source-of-truth change material.

**Inputs:** `repo_path`, `dep_name`, `old_version`, `new_version`

**Outputs:**
- `call_graph`
- `dep_diff`
- `migration_guide`

**Implementation details:**
- Walk all `.py` files with `tree-sitter-python`
- Detect `import dep_name` and `from dep_name import X`
- Trace downstream attribute accesses and function calls
- Record file path, line number, canonical symbol, and a 5-line context window
- Cross-reference tests using a simple symbol search in `test_*.py`, later replaceable with coverage integration
- Fetch source trees for old and new package versions and diff them
- Collect release notes, changelog text, and migration docs

**Invariant:** If `call_graph` is empty, skip semantic migration and open a version-bump-only PR.

### 4.2 Planner Node — LLM

**Purpose:** Derive concrete breaking changes grounded only in the provided dependency diff and migration material, then map them onto actual usage sites.

**System prompt:** `prompts/planner.md`

**Context:**
- Trimmed source diff prioritizing changed signatures
- Migration guide and changelog snippets
- Structured call graph JSON

**Output:** JSON list of `MigrationStep`

**Rules:**
- Must return valid JSON only
- Must not rely on model memory of the library
- Must mark each step as deterministic when a pure AST transform can handle it
- Should also emit `confidence_score` for confidence-gated execution

### 4.3 TestAuditor Node — LLM

**Purpose:** Ensure every affected API surface has meaningful verification, even if the original repo lacks sufficient tests.

**System prompt:** `prompts/test_auditor.md`

**Responsibilities:**
- Generate new tests for uncovered affected symbols
- Update existing tests that no longer reflect the new API semantics
- Prefer standard `pytest` fixtures and no unnecessary external dependencies
- Capture a baseline test run before code modifications begin

**Per-symbol input template:**

```text
Symbol: {symbol}
File where it's used: {file}
Code context: {context}
What changed: {migration_step.notes}
Existing test (if any): {existing_test_code}

Write a pytest test that:
1. Tests the symbol using the NEW API ({migration_step.new_symbol})
2. Asserts the behavior described in the migration step
3. Uses standard pytest fixtures, no external dependencies
```

### 4.4 Coder Node — Hybrid AST + LLM APR Loop

**Purpose:** Apply the migration plan, run tests, use failure feedback, and iterate until pass or retry exhaustion.

**System prompts:**
- `prompts/coder.md`
- `prompts/coder_retry.md`

**Pass 1:**
1. Apply deterministic AST transforms first
2. Write all `test_specs` to disk
3. Use the LLM for remaining semantic changes
4. Run the sandbox

**Retry passes:**
1. Inject failing test names
2. Inject stderr/stdout tail
3. Inject exact prior diff
4. Inject the specific migration step under repair
5. Ask the model to repair only the failures
6. Re-run the sandbox

**Trace capture:**
- Each attempt appends a `StepTrace`
- These traces become the basis for later SFT, DPO, and GRPO workflows

### 4.5 PR Writer Node — Deterministic

**Purpose:** Construct the final PR body and create the pull request via GitHub integration.

**PR body template:**

```markdown
## Graft: Dependency Upgrade — {dep_name} {old_version} → {new_version}

### Breaking Changes Detected
{migration_plan summary table}

### Affected Call Sites
{call_graph summary}

### Tests
- Pre-existing tests modified: {count}
- New tests written by Graft: {count}
- Test result: {N}/{total} passing after {retry_count} attempt(s)

### Attempt History
{attempt_traces summary}

> This PR was created by Graft. All changes require manual review before merging.
```

If the planner marked the job as low confidence, the PR body should surface that clearly.

## 5. Tooling Layer

All tools are thin wrappers over deterministic functionality or sandbox execution.

```python
# agent/tools/
read_file(path: str) -> str
write_file(path: str, content: str) -> None
apply_patch(path: str, unified_diff: str) -> str
search_symbol(repo_path: str, symbol: str) -> list[DepUsage]
run_tests(repo_path: str, test_filter: str | None) -> SandboxResult
fetch_dep_source(dep: str, version: str, symbol: str) -> str
fetch_dep_diff(dep: str, old_v: str, new_v: str) -> str
fetch_migration_guide(dep: str, old_v: str, new_v: str) -> str
create_github_pr(repo: str, branch: str, title: str, body: str) -> str
```

### Tool modules
- `agent/tools/sandbox.py` — sandbox lifecycle and structured test execution
- `agent/tools/ast_transforms.py` — LibCST-based deterministic transforms
- `agent/tools/github.py` — GitHub API interactions, branch creation, PR creation
- `agent/tools/registry.py` — dependency version detection and webhook ingestion
- `agent/tools/registry.py` or equivalent helper also maintains package source fetching helpers

`run_tests` is the only async-heavy tool because sandbox startup and execution may take longer than local file operations.

## 6. Prompt Storage

Prompts live in versioned Markdown files with YAML frontmatter.

```text
graft-agent/
└── prompts/
    ├── planner.md
    ├── test_auditor.md
    ├── coder.md
    └── coder_retry.md
```

Example:

```markdown
---
node: coder
version: 1
model_hint: qwen3-coder
max_tokens: 2048
---

You are Graft's code transformation agent. Your job is to apply
dependency migration changes to Python source files.

## Rules
- Only modify lines that use the changed symbol
- Preserve formatting, comments, and surrounding code
- Output a unified diff, not full files
```

Runtime loader:

```python
# agent/prompts.py
import frontmatter
from pathlib import Path

def load_prompt(name: str) -> tuple[str, dict]:
    raw = (Path("prompts") / f"{name}.md").read_text()
    post = frontmatter.loads(raw)
    return post.content, post.metadata
```

This separates prompt iteration from Python implementation work and lets prompt versions be tracked in git.

## 7. LLM Backend

All model calls go through a single OpenAI-compatible client interface.

```python
# agent/llm.py
from openai import AsyncOpenAI
from functools import lru_cache

@lru_cache
def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )

async def call_llm(
    prompt: str,
    system: str,
    model: str | None = None,
    tools: list | None = None,
    response_format: dict | None = None,
) -> str:
    client = get_client()
    resp = await client.chat.completions.create(
        model=model or settings.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        tools=tools,
        response_format=response_format,
        max_tokens=settings.llm_max_tokens,
    )
    return resp.choices[0].message.content
```

Example environment settings:

```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-...
LLM_MODEL=qwen/qwen3-coder
LLM_MAX_TOKENS=2048
```

Switching providers or moving to a local vLLM endpoint should require only configuration changes.

## 8. FastAPI System Design

### 8.1 Architecture

```text
┌─────────────────────────────────────────┐
│              FastAPI App                │
│                                         │
│  POST /jobs            → enqueue job    │
│  GET  /jobs/{id}       → poll status    │
│  GET  /jobs/{id}/trace → full trace     │
│  GET  /jobs/{id}/stream → SSE stream    │
│  POST /jobs/{id}/cancel                 │
│  GET  /health                           │
└──────────────┬──────────────────────────┘
               │ async task
               ▼
┌─────────────────────────────────────────┐
│           ARQ Job Queue (Redis)         │
│   Worker runs LangGraph, persists state │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      LangGraph + PostgresSaver          │
│   Durable checkpoints and crash resume  │
└─────────────────────────────────────────┘
```

### 8.2 Why this stack
- **ARQ over Celery:** simpler async fit with FastAPI
- **Redis:** queue backend
- **PostgresSaver:** long-running jobs can resume after worker crashes
- **SSE endpoint:** simple real-time progress updates for CLI or frontend consumers

### 8.3 Project Structure

```text
graft-agent/
├── agent/
│   ├── state.py
│   ├── graph.py
│   ├── llm.py
│   ├── prompts.py
│   ├── nodes/
│   │   ├── reader.py
│   │   ├── planner.py
│   │   ├── test_auditor.py
│   │   ├── coder.py
│   │   └── pr_writer.py
│   └── tools/
│       ├── sandbox.py
│       ├── registry.py
│       ├── ast_transforms.py
│       └── github.py
├── api/
│   ├── main.py
│   ├── routes/
│   │   └── jobs.py
│   ├── schemas.py
│   ├── worker.py
│   └── settings.py
├── training/
│   ├── collect.py
│   ├── dpo/
│   │   └── build_pairs.py
│   ├── sft/
│   │   └── train.py
│   ├── grpo/
│   │   └── train.py
│   └── env/
│       └── graft_env.py
├── prompts/
│   ├── planner.md
│   ├── test_auditor.md
│   ├── coder.md
│   └── coder_retry.md
├── pyproject.toml
└── .env.example
```

### 8.4 API Endpoints

#### `POST /jobs`
```json
{
  "repo_path": "/tmp/cloned/myrepo",
  "dep_name": "httpx",
  "old_version": "0.25.0",
  "new_version": "0.27.0"
}
```

#### `GET /jobs/{job_id}`
Returns job status, current node, retry count, detected breaking changes, affected file count, and latest test results.

#### `GET /jobs/{job_id}/trace`
Returns full call graph, migration plan, test specs, attempt traces, and LLM call metadata.

#### `GET /jobs/{job_id}/stream`
Server-Sent Events feed of node transitions and retries.

#### `POST /jobs/{job_id}/cancel`
Interrupts a running job.

#### `GET /health`
Returns service status, queue depth, worker count, and current configured LLM backend.

## 9. Training Pipeline

Graft is intentionally designed to generate training data as it operates.

### 9.1 Collected trajectory data
Each attempt trace stores:
- Prompt context
- Diff output
- Test outcome
- Optional reward
- Attempt index

This gives a clean `(prompt, completion, reward)` structure.

### 9.2 SFT sample conversion

```python
# training/collect.py

def trace_to_sft_sample(trace: StepTrace, state: GraftState) -> dict:
    return {
        "messages": [
            {"role": "system", "content": load_prompt("coder")[0]},
            {"role": "user", "content": build_coder_prompt(trace, state)},
            {"role": "assistant", "content": format_diff(trace["diff"])},
        ],
        "metadata": {
            "job_id": state["job_id"],
            "dep": state["dep_name"],
            "attempt": trace["attempt"],
            "test_pass": trace["test_results"]["passed"],
        }
    }
```

### 9.3 SFT
Use successful traces first to teach output format, prompt conventions, migration reasoning patterns, and diff style.

### 9.4 DPO / negative mining
Failed traces should not be discarded. Pair failed diffs with eventual successful diffs to create chosen/rejected preference data.

### 9.5 GRPO
Use verifiable rewards from actual test execution, not an LLM judge.

```python
# sketch
if tests_pass:
    reward = 1.0 - token_penalty
else:
    reward = partial_pass_rate * 0.5 - 0.1
```

### 9.6 Gym-compatible environment
`training/env/graft_env.py` exposes a single migration step as an RL episode with:
- Observation: prompt context tokens
- Action: diff tokens
- Reward: pass rate after applying diff
- Termination: tests pass or max steps reached

## 10. Innovative Additions

### 10.1 Confidence-gated execution
The planner emits a `confidence_score`. If the score is low, the job is marked low confidence and the PR explicitly warns reviewers.

### 10.2 Symbol-level regression detection
After tests pass, the system can generate follow-up property-style tests to compare important public behavior before and after migration.

### 10.3 Prompt version tracking
Store the git commit hash of each prompt file used in every LLM call for cleaner evaluation across prompt and model changes.

### 10.4 Negative example mining
Use failed attempts as explicit negative preference data rather than throwing them away.

### 10.5 Registry webhook trigger
Instead of only polling PyPI, support registry-triggered job enqueueing as soon as a new version is published.

## 11. Environment Setup

```toml
[project]
name = "graft-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "langgraph>=1.0",
    "langchain-openai",
    "fastapi",
    "uvicorn[standard]",
    "arq",
    "redis",
    "asyncpg",
    "psycopg[binary]",
    "langgraph-checkpoint-postgres",
    "openai",
    "pydantic-settings",
    "python-frontmatter",
    "tree-sitter>=0.23",
    "tree-sitter-python>=0.23",
    "libcst",
    "gitpython",
    "httpx",
    "e2b-code-interpreter",
    "langsmith",
]

[project.optional-dependencies]
training = [
    "torch>=2.3",
    "transformers>=4.47",
    "trl>=0.12",
    "peft>=0.13",
    "datasets",
    "accelerate",
    "bitsandbytes",
    "flash-attn",
    "gymnasium",
]
```

```bash
uv sync
uv sync --extra training
uv run uvicorn api.main:app --reload
uv run arq api.worker.WorkerSettings
```

Example manual invocation:

```bash
uv run python -c "
from agent.graph import build_graph
graph = build_graph(checkpointer=None)
result = graph.invoke({
    'job_id': 'test-001',
    'repo_path': '/tmp/testrepo',
    'dep_name': 'httpx',
    'old_version': '0.25.0',
    'new_version': '0.27.0',
    'retry_count': 0,
    'status': 'pending',
})
print(result['status'])
"
```

## 12. Complete Build Order

This version includes the missing pieces needed to make the implementation sequence complete and executable.

1. **Define state and shared schemas** — implement `agent/state.py` fully, including `test_results_current`, `confidence_score`, and low-confidence flags.
2. **Create prompt files first** — write `prompts/planner.md`, `prompts/test_auditor.md`, `prompts/coder.md`, and `prompts/coder_retry.md` before wiring LLM nodes.
3. **Build prompt loader and settings** — implement `agent/prompts.py`, `api/settings.py`, and `.env.example` so model and service configuration are centralized.
4. **Stub the graph end-to-end** — implement `agent/graph.py` with dummy node returns so a fake job can traverse the graph from `reader` to terminal state.
5. **Implement repo and file utility wrappers** — build `read_file`, `write_file`, `apply_patch`, and helper filesystem utilities.
6. **Build deterministic source analysis** — implement `agent/nodes/reader.py` using tree-sitter and symbol tracing; verify call graph extraction on a real Python repo.
7. **Implement dependency diff + migration material fetchers** — add old/new source fetch, diff generation, and changelog or release-note ingestion helpers.
8. **Implement sandbox execution layer** — build `agent/tools/sandbox.py`; ensure `run_tests()` returns structured `SandboxResult` consistently.
9. **Implement AST transform engine** — build `agent/tools/ast_transforms.py` with LibCST-based renames, import path changes, and safe signature rewrites.
10. **Implement Planner node** — build `agent/nodes/planner.py`; parse only grounded dependency diffs and emit structured `MigrationStep` JSON plus confidence score.
11. **Implement TestAuditor node** — build `agent/nodes/test_auditor.py`; generate runnable pytest tests and capture baseline suite results.
12. **Implement Coder pass 1** — wire deterministic AST transforms plus writing generated tests before any semantic LLM edits.
13. **Implement Coder retry loop** — add semantic LLM edit path, structured retry prompting, error-context injection, and `attempt_traces` recording.
14. **Implement PR writer** — build `agent/nodes/pr_writer.py` to generate deterministic PR bodies from migration plans, test outcomes, and attempt history.
15. **Implement GitHub integration** — add `agent/tools/github.py` for branch creation, commit flow, and pull request creation.
16. **Run end-to-end locally** — test one real migration path such as `httpx 0.25 -> 0.27`, verify that the graph reaches either success or escalate with artifacts intact.
17. **Add API schemas and routes** — implement `api/schemas.py`, `api/routes/jobs.py`, and `api/main.py`.
18. **Add ARQ worker and durable checkpoints** — implement `api/worker.py` plus PostgresSaver checkpointing and crash-resume behavior.
19. **Add streaming and health endpoints** — implement `/jobs/{id}/stream`, `/health`, and cancel support.
20. **Implement registry trigger path** — build `agent/tools/registry.py` or equivalent trigger ingestion for polling first, then webhook-based enqueueing.
21. **Start collecting traces** — implement `training/collect.py` to serialize successful and failed attempts into training-ready records.
22. **Run first SFT pass** — train on successful trajectories to teach prompt and diff format alignment.
23. **Build DPO or preference pairs** — convert failed-vs-successful attempts into chosen/rejected datasets.
24. **Run GRPO** — use real sandboxed test outcomes as rewards for verifiable optimization.
25. **Implement Gym environment** — build `training/env/graft_env.py` for online RL and experimentation.
26. **Add confidence gating and regression checks** — wire low-confidence PR warnings and optional post-pass semantic regression validation.
27. **Only then build SaaS concerns** — tenant isolation, billing, org auth, dashboards, and scaling primitives come after the core agent is already reliable.

## 13. Practical MVP Cut

If the goal is to get a serious non-toy prototype running fast, the shortest credible path is:
- Python only
- GitHub repos only
- `pytest` only
- One sandbox backend
- One deterministic transform engine
- One model backend through OpenAI-compatible APIs
- Manual review only, no auto-merge

That cut is enough to validate the hardest claim: **Graft can upgrade a dependency, repair the app, and prove correctness by passing tests.**
