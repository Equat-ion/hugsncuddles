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
