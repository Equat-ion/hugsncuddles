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
