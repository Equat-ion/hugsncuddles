# Graft Design Spec
Date: 2026-05-06
Status: Awaiting user review

## Summary
Build the full-scope Graft system described in the PRD as a plugin-first, feature-flagged architecture. The repo root is named `graft` and follows the PRD module layout (`agent/`, `api/`, `training/`, `prompts/`). Default sandbox is e2b. Redis + PostgresSaver are wired from day one. GitHub App authentication is used for PR creation. LLM base URL and key are read from `.env`.

## Goals
- End-to-end autonomous dependency upgrade flow for Python repos.
- Deterministic + LLM hybrid loop with retries and audit trail.
- Durable job execution with ARQ + Redis + PostgresSaver.
- Plugin-first tool backends with feature flags.
- FastAPI control plane endpoints and SSE streaming.
- Training data capture pipeline for SFT/DPO/GRPO.

## Non-Goals
- Non-Python ecosystems.
- Auto-merge and SaaS multi-tenant features.
- UI dashboard.

## Architecture Overview
The system is a LangGraph `StateGraph` with nodes:
`reader -> planner -> test_auditor -> coder (retry loop) -> pr_writer`, plus an `escalate` terminal. Each node is a pure function over `GraftState`, while tool backends handle external effects. The worker runs on ARQ (Redis) and persists checkpoints via PostgresSaver for crash-resume. FastAPI exposes job control endpoints.

## Repo Structure
```
graft/
├── agent/
│   ├── state.py
│   ├── graph.py
│   ├── llm.py
│   ├── prompts.py
│   ├── nodes/
│   └── tools/
├── api/
├── training/
├── prompts/
├── pyproject.toml
└── .env.example
```

## Plugin-First Tools
Tools are defined as interfaces with swappable backends. A small registry chooses the backend from settings (env-driven), without changing node code. Key tool categories:
- `sandbox`: default backend `e2b`, with a local runner optional.
- `github`: GitHub App auth for branch/commit/PR.
- `registry`: PyPI polling + webhook ingestion.
- `ast_transforms`: LibCST transforms.
- `fs`: read/write/apply_patch helpers.

## Feature Flags
Feature flags live in `api/settings.py` and gate execution paths, not code presence:
- `ENABLE_TRAINING`
- `ENABLE_REGISTRY_TRIGGERS`
- `ENABLE_REGRESSION_CHECKS`
- `ENABLE_STREAMING`

## State and Data Flow
1. `POST /jobs` enqueues a job with repo path and dependency versions.
2. Worker loads graph with PostgresSaver checkpointer.
3. Reader builds `call_graph`, dependency diffs, and migration materials.
4. Planner emits `migration_plan` and confidence score.
5. TestAuditor writes tests and runs a baseline test suite.
6. Coder applies deterministic transforms, then LLM edits, runs sandbox tests, and retries on failure.
7. PRWriter generates a structured PR body and invokes GitHub backend.

Artifacts are stored in `GraftState`: test results, diffs, attempt traces, PR URL, and confidence flags.

## Node Behaviors
### Reader (deterministic)
- Parses Python files with tree-sitter to locate dependency usage.
- Computes diff between old/new dep versions and fetches migration docs.
- If no usage is found, short-circuits to a version-bump-only PR.

### Planner (LLM)
- Uses only provided diffs and migration material.
- Outputs JSON-only `MigrationStep` list plus confidence score.

### TestAuditor (LLM)
- Ensures each affected symbol has tests, writing new pytest tests when needed.
- Captures baseline test run before any code changes.

### Coder (hybrid)
- Applies deterministic LibCST transforms first.
- Writes generated tests before semantic LLM edits.
- Runs sandbox tests and retries up to MAX_RETRIES with targeted context.
- Appends `StepTrace` for each attempt.

### PRWriter (deterministic)
- Generates PR body from state and creates PR via GitHub tool.
- Surfaces low-confidence warnings in the PR body.

## Error Handling and Retry Policy
- Retries are capped by MAX_RETRIES; each retry narrows context to failing tests and relevant migration steps.
- If retry cap is hit, status becomes `escalate` with full trace preserved.
- Planner low confidence is preserved and surfaced in PR.

## API Surface
- `POST /jobs` create job
- `GET /jobs/{id}` status
- `GET /jobs/{id}/trace` full trace
- `GET /jobs/{id}/stream` SSE stream
- `POST /jobs/{id}/cancel` cancel
- `GET /health` service health

## Configuration
Settings in `api/settings.py` (Pydantic Settings). LLM base URL and key are read from `.env` (Hack Club AI values provided by user). GitHub App credentials are read from env. Redis and Postgres connection URLs are required for worker startup.

## Security and Access
- GitHub App authentication for repo access and PR creation.
- No secrets stored in state; only references or minimal metadata.

## Training Pipeline
- `training/collect.py` captures traces into SFT-ready format.
- DPO/GRPO utilities generate preference data and use test results as rewards.
- All training is gated by `ENABLE_TRAINING`.

## Out of Scope (v1)
- Multi-language repos
- Auto-merge and billing/auth systems
- UI dashboard

## Open Decisions (resolved)
- Repo root name: `graft`
- Sandbox default: e2b
- Checkpointing: PostgresSaver + Redis
- GitHub auth: GitHub App
- LLM base URL/key: from `.env`
