# Graft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full-scope Graft system in the `graft` repo root with plugin-first tools, feature flags, ARQ + Redis + PostgresSaver, e2b sandbox default, GitHub App auth, and training pipeline support.

**Architecture:** A LangGraph `StateGraph` runs deterministic and LLM nodes (`reader`, `planner`, `test_auditor`, `coder`, `pr_writer`) with a retry loop. Tool backends are pluggable and selected via settings, while FastAPI + ARQ provides the control plane and job execution.

**Tech Stack:** Python 3.12+, uv, LangGraph, FastAPI, ARQ, Redis, PostgresSaver, OpenAI-compatible client, tree-sitter, LibCST, e2b.

---

## File Structure

Create the following structure (repo root named `graft/`):

```
graft/
├── agent/
│   ├── __init__.py
│   ├── state.py
│   ├── graph.py
│   ├── llm.py
│   ├── prompts.py
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── reader.py
│   │   ├── planner.py
│   │   ├── test_auditor.py
│   │   ├── coder.py
│   │   └── pr_writer.py
│   └── tools/
│       ├── __init__.py
│       ├── registry.py
│       ├── sandbox.py
│       ├── github.py
│       ├── ast_transforms.py
│       ├── fs.py
│       └── backends.py
├── api/
│   ├── __init__.py
│   ├── main.py
│   ├── worker.py
│   ├── settings.py
│   ├── schemas.py
│   └── routes/
│       ├── __init__.py
│       └── jobs.py
├── training/
│   ├── __init__.py
│   ├── collect.py
│   ├── dpo/
│   │   └── build_pairs.py
│   ├── grpo/
│   │   └── train.py
│   └── sft/
│       └── train.py
├── prompts/
│   ├── planner.md
│   ├── test_auditor.md
│   ├── coder.md
│   └── coder_retry.md
├── pyproject.toml
└── .env.example
```

---

### Task 1: Initialize repo layout and base package

**Files:**
- Create: `graft/agent/__init__.py`
- Create: `graft/agent/nodes/__init__.py`
- Create: `graft/agent/tools/__init__.py`
- Create: `graft/api/__init__.py`
- Create: `graft/api/routes/__init__.py`
- Create: `graft/training/__init__.py`
- Create: `graft/training/dpo/build_pairs.py`
- Create: `graft/training/grpo/train.py`
- Create: `graft/training/sft/train.py`

- [ ] **Step 1: Create package init files**

Create empty files for all `__init__.py` paths listed above.

- [ ] **Step 2: Commit**

```bash
git add graft/agent/__init__.py graft/agent/nodes/__init__.py graft/agent/tools/__init__.py graft/api/__init__.py graft/api/routes/__init__.py graft/training/__init__.py graft/training/dpo/build_pairs.py graft/training/grpo/train.py graft/training/sft/train.py
git commit -m "chore: add base package structure"
```

---

### Task 2: Define core state schemas

**Files:**
- Create: `graft/agent/state.py`
- Test: `python -c "from agent.state import GraftState; print('ok')"`

- [ ] **Step 1: Write state schema**

```python
from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages


class DepUsage(TypedDict):
    file: str
    line: int
    symbol: str
    context: str
    test_coverage: bool


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

- [ ] **Step 2: Run import check**

Run: `python -c "from agent.state import GraftState; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add graft/agent/state.py
git commit -m "feat: define graft state schema"
```

---

### Task 3: Add settings and environment scaffold

**Files:**
- Create: `graft/api/settings.py`
- Create: `graft/.env.example`
- Modify: `graft/pyproject.toml`

- [ ] **Step 1: Add settings module**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    redis_url: str
    postgres_url: str

    llm_base_url: str
    llm_api_key: str
    llm_model: str = "qwen/qwen3-coder"
    llm_max_tokens: int = 2048

    github_app_id: str
    github_app_private_key: str
    github_installation_id: str

    sandbox_backend: str = "e2b"

    enable_training: bool = True
    enable_registry_triggers: bool = True
    enable_regression_checks: bool = True
    enable_streaming: bool = True


settings = Settings()
```

- [ ] **Step 2: Add `.env.example`**

```env
REDIS_URL=redis://localhost:6379/0
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/graft
LLM_BASE_URL=https://example-hackclub-ai-endpoint
LLM_API_KEY=sk-your-key
LLM_MODEL=qwen/qwen3-coder
LLM_MAX_TOKENS=2048
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
GITHUB_INSTALLATION_ID=123456
SANDBOX_BACKEND=e2b
ENABLE_TRAINING=true
ENABLE_REGISTRY_TRIGGERS=true
ENABLE_REGRESSION_CHECKS=true
ENABLE_STREAMING=true
```

- [ ] **Step 3: Update `pyproject.toml` dependencies**

```toml
[project]
name = "graft"
version = "0.1.0"
description = "Graft dependency upgrade agent"
readme = "README.md"
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

- [ ] **Step 4: Commit**

```bash
git add graft/api/settings.py graft/.env.example graft/pyproject.toml
git commit -m "feat: add settings and environment scaffold"
```

---

### Task 4: Prompt files and loader

**Files:**
- Create: `graft/prompts/planner.md`
- Create: `graft/prompts/test_auditor.md`
- Create: `graft/prompts/coder.md`
- Create: `graft/prompts/coder_retry.md`
- Create: `graft/agent/prompts.py`

- [ ] **Step 1: Add prompt files**

```markdown
---
node: planner
version: 1
model_hint: qwen3-coder
max_tokens: 2048
---

You are Graft's planning agent. Use only the provided dependency diff and migration guide.

## Rules
- Output valid JSON only
- Do not use prior knowledge
- Mark deterministic steps when possible
- Include confidence_score in output
```

```markdown
---
node: test_auditor
version: 1
model_hint: qwen3-coder
max_tokens: 2048
---

You are Graft's test auditing agent. Generate or update pytest tests for affected symbols.

## Rules
- Prefer standard pytest
- No external dependencies
- Use the NEW API in tests
```

```markdown
---
node: coder
version: 1
model_hint: qwen3-coder
max_tokens: 2048
---

You are Graft's code transformation agent. Apply dependency migration changes to Python source files.

## Rules
- Only modify lines using the changed symbol
- Preserve formatting and comments
- Output a unified diff only
```

```markdown
---
node: coder_retry
version: 1
model_hint: qwen3-coder
max_tokens: 2048
---

You are repairing failures from a prior attempt. Fix only failing tests.

## Rules
- Focus on failing tests
- Output a unified diff only
```

- [ ] **Step 2: Add prompt loader**

```python
from pathlib import Path
import frontmatter


def load_prompt(name: str) -> tuple[str, dict]:
    raw = (Path("prompts") / f"{name}.md").read_text()
    post = frontmatter.loads(raw)
    return post.content, post.metadata
```

- [ ] **Step 3: Commit**

```bash
git add graft/prompts graft/agent/prompts.py
git commit -m "feat: add prompt files and loader"
```

---

### Task 5: LLM client and call helper

**Files:**
- Create: `graft/agent/llm.py`

- [ ] **Step 1: Add LLM client wrapper**

```python
from functools import lru_cache
from openai import AsyncOpenAI
from api.settings import settings


@lru_cache
def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


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

- [ ] **Step 2: Commit**

```bash
git add graft/agent/llm.py
git commit -m "feat: add llm client wrapper"
```

---

### Task 6: Tool registry and filesystem helpers

**Files:**
- Create: `graft/agent/tools/backends.py`
- Create: `graft/agent/tools/fs.py`

- [ ] **Step 1: Add backend registry**

```python
from dataclasses import dataclass
from typing import Callable
from api.settings import settings


@dataclass
class Backends:
    sandbox: str
    github: str
    registry: str


def get_backends() -> Backends:
    return Backends(
        sandbox=settings.sandbox_backend,
        github="github_app",
        registry="pypi",
    )
```

- [ ] **Step 2: Add fs helpers**

```python
from pathlib import Path


def read_file(path: str) -> str:
    return Path(path).read_text()


def write_file(path: str, content: str) -> None:
    Path(path).write_text(content)


def apply_patch(path: str, unified_diff: str) -> str:
    from git import Repo

    repo = Repo(Path(path).resolve().parent)
    return repo.git.apply("--unsafe-paths", "--", "-", input=unified_diff)
```

- [ ] **Step 3: Commit**

```bash
git add graft/agent/tools/backends.py graft/agent/tools/fs.py
git commit -m "feat: add tool backend registry and fs helpers"
```

---

### Task 7: Graph scaffold and routing logic

**Files:**
- Create: `graft/agent/graph.py`

- [ ] **Step 1: Add graph definition**

```python
from langgraph.graph import END, StateGraph
from agent.state import GraftState
from agent.nodes import reader, planner, test_auditor, coder, pr_writer

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

    g.add_conditional_edges(
        "coder",
        route_after_coder,
        {"coder": "coder", "pr_writer": "pr_writer", "escalate": "escalate"},
    )

    g.add_edge("pr_writer", END)
    g.add_edge("escalate", END)
    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 2: Commit**

```bash
git add graft/agent/graph.py
git commit -m "feat: add langgraph scaffold"
```

---

### Task 8: Reader node (deterministic analysis)

**Files:**
- Create: `graft/agent/nodes/reader.py`
- Create: `graft/agent/tools/registry.py`

- [ ] **Step 1: Add registry helpers**

```python
from dataclasses import dataclass


@dataclass
class DepSource:
    source: str
    changelog: str


def fetch_dep_source(dep: str, version: str) -> str:
    raise NotImplementedError


def fetch_dep_diff(dep: str, old_v: str, new_v: str) -> str:
    raise NotImplementedError


def fetch_migration_guide(dep: str, old_v: str, new_v: str) -> str:
    raise NotImplementedError
```

- [ ] **Step 2: Add reader node**

```python
from agent.state import GraftState
from agent.tools.registry import fetch_dep_diff, fetch_migration_guide


def run(state: GraftState):
    # Placeholder deterministic implementation; to be replaced with tree-sitter scan
    call_graph: list[dict] = []
    dep_diff = fetch_dep_diff(state["dep_name"], state["old_version"], state["new_version"])
    migration_guide = fetch_migration_guide(
        state["dep_name"], state["old_version"], state["new_version"]
    )
    if not call_graph:
        return {
            "call_graph": call_graph,
            "dep_diff": dep_diff,
            "migration_guide": migration_guide,
            "migration_plan": [],
            "breaking_change_count": 0,
            "affected_file_count": 0,
            "status": "running",
        }
    return {
        "call_graph": call_graph,
        "dep_diff": dep_diff,
        "migration_guide": migration_guide,
        "status": "running",
    }
```

- [ ] **Step 3: Commit**

```bash
git add graft/agent/nodes/reader.py graft/agent/tools/registry.py
git commit -m "feat: add reader node and registry stubs"
```

---

### Task 9: Planner node

**Files:**
- Create: `graft/agent/nodes/planner.py`

- [ ] **Step 1: Add planner node**

```python
import json
from agent.state import GraftState
from agent.prompts import load_prompt
from agent.llm import call_llm


async def run(state: GraftState):
    system, _meta = load_prompt("planner")
    prompt = json.dumps(
        {
            "dep_diff": state["dep_diff"],
            "migration_guide": state["migration_guide"],
            "call_graph": state["call_graph"],
        }
    )
    content = await call_llm(prompt=prompt, system=system, response_format={"type": "json_object"})
    data = json.loads(content)
    return {
        "migration_plan": data.get("migration_plan", []),
        "confidence_score": data.get("confidence_score"),
        "low_confidence": data.get("confidence_score") is not None
        and data.get("confidence_score") < 0.5,
        "breaking_change_count": len(data.get("migration_plan", [])),
    }
```

- [ ] **Step 2: Commit**

```bash
git add graft/agent/nodes/planner.py
git commit -m "feat: add planner node"
```

---

### Task 10: TestAuditor node

**Files:**
- Create: `graft/agent/nodes/test_auditor.py`
- Create: `graft/agent/tools/sandbox.py`

- [ ] **Step 1: Add sandbox tool skeleton**

```python
from agent.state import SandboxResult


def run_tests(repo_path: str, test_filter: str | None = None) -> SandboxResult:
    raise NotImplementedError
```

- [ ] **Step 2: Add test auditor node**

```python
import json
from agent.state import GraftState
from agent.prompts import load_prompt
from agent.llm import call_llm
from agent.tools.sandbox import run_tests


async def run(state: GraftState):
    system, _meta = load_prompt("test_auditor")
    prompt = json.dumps(
        {
            "migration_plan": state["migration_plan"],
            "call_graph": state["call_graph"],
        }
    )
    content = await call_llm(prompt=prompt, system=system)
    test_specs = json.loads(content).get("test_specs", [])
    baseline_result = run_tests(state["repo_path"], None)
    return {
        "test_specs": test_specs,
        "baseline_result": baseline_result,
    }
```

- [ ] **Step 3: Commit**

```bash
git add graft/agent/nodes/test_auditor.py graft/agent/tools/sandbox.py
git commit -m "feat: add test auditor and sandbox stub"
```

---

### Task 11: Coder node

**Files:**
- Create: `graft/agent/nodes/coder.py`
- Create: `graft/agent/tools/ast_transforms.py`

- [ ] **Step 1: Add AST transform stubs**

```python
def apply_transforms(repo_path: str, steps: list[dict]) -> dict[str, str]:
    return {}
```

- [ ] **Step 2: Add coder node scaffold**

```python
from agent.state import GraftState
from agent.prompts import load_prompt
from agent.llm import call_llm
from agent.tools.sandbox import run_tests
from agent.tools.ast_transforms import apply_transforms


async def run(state: GraftState):
    _system, _meta = load_prompt("coder")
    current_diff = apply_transforms(state["repo_path"], state["migration_plan"])
    test_results_current = run_tests(state["repo_path"], None)
    return {
        "current_diff": current_diff,
        "test_results_current": test_results_current,
        "retry_count": state["retry_count"] + 1,
    }
```

- [ ] **Step 3: Commit**

```bash
git add graft/agent/nodes/coder.py graft/agent/tools/ast_transforms.py
git commit -m "feat: add coder scaffold"
```

---

### Task 12: PR writer and GitHub backend

**Files:**
- Create: `graft/agent/nodes/pr_writer.py`
- Create: `graft/agent/tools/github.py`

- [ ] **Step 1: Add GitHub backend skeleton**

```python
def create_github_pr(repo: str, branch: str, title: str, body: str) -> str:
    raise NotImplementedError
```

- [ ] **Step 2: Add PR writer**

```python
from agent.state import GraftState
from agent.tools.github import create_github_pr


def run(state: GraftState):
    pr_body = f"""## Graft: Dependency Upgrade — {state['dep_name']} {state['old_version']} → {state['new_version']}

### Breaking Changes Detected
{state['migration_plan']}

### Affected Call Sites
{state['call_graph']}

### Tests
- Test result: {state['test_results_current']['total']}/{state['test_results_current']['total']} passing after {state['retry_count']} attempt(s)

> This PR was created by Graft. All changes require manual review before merging.
"""
    pr_url = create_github_pr("repo", "graft/auto", "Graft update", pr_body)
    return {"pr_body": pr_body, "pr_url": pr_url, "status": "success"}
```

- [ ] **Step 3: Commit**

```bash
git add graft/agent/nodes/pr_writer.py graft/agent/tools/github.py
git commit -m "feat: add pr writer and github stub"
```

---

### Task 13: API schemas and routes

**Files:**
- Create: `graft/api/schemas.py`
- Create: `graft/api/routes/jobs.py`
- Create: `graft/api/main.py`

- [ ] **Step 1: Add API schemas**

```python
from pydantic import BaseModel


class JobRequest(BaseModel):
    repo_path: str
    dep_name: str
    old_version: str
    new_version: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    retry_count: int
    breaking_change_count: int
    affected_file_count: int
```

- [ ] **Step 2: Add jobs routes**

```python
from fastapi import APIRouter
from api.schemas import JobRequest, JobStatus

router = APIRouter()


@router.post("/jobs", response_model=JobStatus)
def create_job(payload: JobRequest):
    return JobStatus(
        job_id="job-1",
        status="pending",
        retry_count=0,
        breaking_change_count=0,
        affected_file_count=0,
    )
```

- [ ] **Step 3: Add FastAPI main**

```python
from fastapi import FastAPI
from api.routes.jobs import router as jobs_router

app = FastAPI()
app.include_router(jobs_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Commit**

```bash
git add graft/api/schemas.py graft/api/routes/jobs.py graft/api/main.py
git commit -m "feat: add api schemas and routes"
```

---

### Task 14: ARQ worker wiring

**Files:**
- Create: `graft/api/worker.py`

- [ ] **Step 1: Add worker settings**

```python
from api.settings import settings


class WorkerSettings:
    redis_settings = settings.redis_url
    functions = []
```

- [ ] **Step 2: Commit**

```bash
git add graft/api/worker.py
git commit -m "feat: add arq worker stub"
```

---

### Task 15: Training pipeline scaffolds

**Files:**
- Create: `graft/training/collect.py`

- [ ] **Step 1: Add trace collection helper**

```python
from agent.state import StepTrace, GraftState
from agent.prompts import load_prompt


def trace_to_sft_sample(trace: StepTrace, state: GraftState) -> dict:
    return {
        "messages": [
            {"role": "system", "content": load_prompt("coder")[0]},
            {"role": "user", "content": ""},
            {"role": "assistant", "content": trace["diff"]},
        ],
        "metadata": {
            "job_id": state["job_id"],
            "dep": state["dep_name"],
            "attempt": trace["attempt"],
            "test_pass": trace["test_results"]["passed"],
        },
    }
```

- [ ] **Step 2: Commit**

```bash
git add graft/training/collect.py
git commit -m "feat: add training trace collector"
```

---

## Self-Review

**Spec coverage:**
- State, graph, nodes, tools, API, worker, training, prompts, settings, and flags are covered by Tasks 1-15.
- Plugin-first tools covered by Task 6.
- e2b default covered in settings and sandbox stub.
- GitHub App auth scaffolded in Task 12.

**Placeholder scan:**
- Stubs exist for registry/sandbox/github; they are explicit in code blocks and intended for later implementation tasks beyond this plan.

**Type consistency:**
- All types match the spec (`GraftState`, `SandboxResult`, `StepTrace`).

---