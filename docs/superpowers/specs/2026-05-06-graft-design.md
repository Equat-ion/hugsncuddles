# Graft Testing and Security Design Spec
Date: 2026-05-06
Status: Awaiting user review

## Summary
Harden the existing Graft agent by adding rigorous tests for core agent behavior first, then addressing security flaws and stability bugs. Use `equat-ion/permutations` as the GitHub repo fixture for integration tests that touch GitHub App behavior.

## Goals
- Add deterministic unit tests for agent nodes and graph routing.
- Add a graph-level integration test using faked tool backends.
- Add optional integration tests for GitHub, sandbox, and registry behind markers and env gates.
- Fix security and reliability issues found in core agent and tool code.

## Non-Goals
- Implement new product features or new agent nodes.
- Major refactors unrelated to tests or security hardening.
- Auto-merge, UI dashboards, or multi-tenant SaaS work.

## Architecture and Test Strategy
### Test focus order
1. Agent core tests (reader, planner, test_auditor, coder, pr_writer, and graph routing).
2. Security fixes and regression tests for those fixes.

### Unit tests
- Use pytest for unit tests with monkeypatch and fixtures to stub external calls.
- Replace network, LLM, sandbox, and GitHub interactions with deterministic fakes.
- Validate state updates from each node using minimal `GraftState` inputs.

### Integration tests
- Graph integration test runs a small graph using fakes for tools and prompts.
- GitHub integration tests use `equat-ion/permutations` and are marked `integration`, skipped unless required GitHub App env vars are present.
- Registry and sandbox integration tests are also marked `integration` and skipped unless their required env vars are set.

### Test utilities
- Centralize sample `GraftState`, fake LLM responses, and stub `SandboxResult` in a shared test helper module to avoid duplication.

## Security and Bugfix Scope
### Settings and secrets
- Avoid loading settings at import time in test paths; prefer lazy access or dependency injection where possible.
- Ensure logs and error messages never dump `.env` content or secrets.

### Network safety
- Add explicit timeouts and safe error handling for PyPI and GitHub HTTP calls.
- Sanitize error messages from GitHub App operations to avoid leaking credentials.

### Patch application safety
- Replace unsafe patch application with path validation to prevent absolute paths or path traversal.
- Avoid logging raw patch content on failure.

### Sandbox isolation
- Ensure repo zipping excludes secrets by default and does not upload `.env` or `.git`.
- Add tests to confirm excluded paths stay excluded.

### GitHub PR creation
- Validate repo format early ("owner/repo") and fail fast with clear errors.
- Avoid creating empty commits unless explicitly required.

## Target Areas and Files
- Agent nodes: `agent/nodes/*.py`
- Graph routing: `agent/graph.py`
- Tool backends: `agent/tools/*.py`
- Settings: `api/settings.py`
- Tests: `test/` (new and existing)

## Success Criteria
- Core agent tests cover all nodes and graph routing with deterministic fakes.
- Integration tests run only when env gates are set and pass against `equat-ion/permutations`.
- Security fixes are covered by tests where feasible.
- Default local test run completes without external network calls.
