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
