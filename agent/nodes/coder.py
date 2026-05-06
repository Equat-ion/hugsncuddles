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
