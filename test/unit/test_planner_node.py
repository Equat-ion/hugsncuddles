import asyncio

import pytest


def test_planner_parses_confidence(monkeypatch):
    from agent.nodes import planner
    from test.helpers.fakes import fake_state, fake_llm_json

    async def fake_call_llm(**kwargs):
        return fake_llm_json({"migration_plan": [{"id": "1"}], "confidence_score": 0.4})

    monkeypatch.setattr(planner, "load_prompt", lambda _: ("sys", {}))
    monkeypatch.setattr(planner, "call_llm", fake_call_llm)

    result = asyncio.run(planner.run(fake_state()))
    assert result["breaking_change_count"] == 1
    assert result["low_confidence"] is True