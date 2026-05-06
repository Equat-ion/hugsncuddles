import asyncio
import pytest


@pytest.mark.integration
def test_graph_routes_to_pr_writer(monkeypatch):
    from agent import graph
    from test.helpers.fakes import fake_state, fake_sandbox_result

    def fake_reader(state):
        return {"dep_diff": "d", "migration_guide": "g", "call_graph": []}

    async def fake_planner(_state):
        return {"migration_plan": [], "confidence_score": 0.9, "low_confidence": False, "breaking_change_count": 0}

    async def fake_test_auditor(_state):
        return {"test_specs": [], "baseline_result": fake_sandbox_result(passed=True)}

    async def fake_coder(_state):
        return {"test_results_current": fake_sandbox_result(passed=True), "retry_count": 1, "current_diff": {}}

    monkeypatch.setattr(graph.reader, "run", fake_reader)
    monkeypatch.setattr(graph.planner, "run", fake_planner)
    monkeypatch.setattr(graph.test_auditor, "run", fake_test_auditor)
    monkeypatch.setattr(graph.coder, "run", fake_coder)

    g = graph.build_graph(checkpointer=None)
    final = asyncio.run(g.ainvoke(fake_state()))
    assert final["status"] in ("success", "escalate", "running")