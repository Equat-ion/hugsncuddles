import os
import pytest


@pytest.mark.integration
def test_github_app_can_read_repo():
    from agent.tools.github import _get_github_for_installation

    if not os.environ.get("GITHUB_APP_ID"):
        pytest.skip("missing GitHub App env vars")

    g = _get_github_for_installation()
    repo = g.get_repo("equat-ion/permutations")
    assert repo.full_name == "equat-ion/permutations"