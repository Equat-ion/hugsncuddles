import asyncio

import pytest


def test_coder_increments_retry(monkeypatch):
    from agent.nodes import coder
    from test.helpers.fakes import fake_state, fake_sandbox_result

    monkeypatch.setattr(coder, "load_prompt", lambda _: ("sys", {}))
    monkeypatch.setattr(coder, "apply_transforms", lambda *_: {"file.py": ""})
    monkeypatch.setattr(coder, "run_tests", lambda *_: fake_sandbox_result(passed=True))

    result = asyncio.run(coder.run(fake_state(retry_count=1)))
    assert result["retry_count"] == 2