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
