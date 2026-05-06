from __future__ import annotations

import json
from typing import Any

from agent.state import GraftState, SandboxResult


def fake_state(**overrides: Any) -> GraftState:
    base: GraftState = {
        "job_id": "test-001",
        "repo_path": "/tmp/repo",
        "dep_name": "requests",
        "old_version": "2.28.0",
        "new_version": "2.32.0",
        "call_graph": [],
        "dep_diff": "",
        "migration_guide": "",
        "migration_plan": [],
        "breaking_change_count": 0,
        "affected_file_count": 0,
        "confidence_score": None,
        "low_confidence": None,
        "test_specs": [],
        "baseline_result": fake_sandbox_result(),
        "test_results_current": fake_sandbox_result(),
        "current_diff": {},
        "attempt_traces": [],
        "retry_count": 0,
        "status": "pending",
        "pr_body": None,
        "pr_url": None,
        "messages": [],
    }
    base.update(overrides)
    return base


def fake_sandbox_result(passed: bool = True, total: int = 1) -> SandboxResult:
    return {
        "passed": passed,
        "total": total,
        "failed_names": [],
        "errors": [],
        "stdout": "",
        "duration_ms": 1,
    }


def fake_llm_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload)