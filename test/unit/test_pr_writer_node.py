import pytest


def test_pr_writer_uses_repo_owner_format(monkeypatch):
    from agent.nodes import pr_writer
    from test.helpers.fakes import fake_state

    called = {}

    def fake_create_pr(**kwargs):
        called.update(kwargs)
        return "https://example.com/pr/1"

    monkeypatch.setattr(pr_writer, "create_github_pr", fake_create_pr)
    state = fake_state(repo_path="equat-ion/permutations")
    result = pr_writer.run(state)
    assert called["repo"] == "equat-ion/permutations"
    assert result["status"] == "success"