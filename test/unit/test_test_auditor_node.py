import asyncio

import pytest


def test_test_auditor_uses_injected_runner(monkeypatch):
    from agent.nodes import test_auditor
    from test.helpers.fakes import fake_state, fake_llm_json, fake_sandbox_result

    async def fake_call_llm(**kwargs):
        return fake_llm_json({"test_specs": []})

    monkeypatch.setattr(test_auditor, "load_prompt", lambda _: ("sys", {}))
    monkeypatch.setattr(test_auditor, "call_llm", fake_call_llm)

    def fake_run(_repo, _filter=None):
        return fake_sandbox_result(passed=False)

    result = asyncio.run(test_auditor.run(fake_state(), run_tests=fake_run))
    assert result["baseline_result"]["passed"] is False