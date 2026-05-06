import json
from agent.state import GraftState
from agent.prompts import load_prompt
from agent.llm import call_llm
from agent.tools.sandbox import run_tests


async def run(state: GraftState, run_tests=None):
    if run_tests is None:
        from agent.tools.sandbox import run_tests as default_run_tests
        run_tests = default_run_tests

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
