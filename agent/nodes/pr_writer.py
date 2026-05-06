from agent.state import GraftState
from agent.tools.github import create_github_pr


def run(state: GraftState):
    pr_body = f"""## Graft: Dependency Upgrade — {state['dep_name']} {state['old_version']} → {state['new_version']}

### Breaking Changes Detected
{state['migration_plan']}

### Affected Call Sites
{state['call_graph']}

### Tests
- Test result: {state['test_results_current']['total']}/{state['test_results_current']['total']} passing after {state['retry_count']} attempt(s)

> This PR was created by Graft. All changes require manual review before merging.
"""
    pr_url = create_github_pr(
        repo=state["repo_path"],          # expects "owner/repo" format
        branch=f"graft/upgrade-{state['dep_name'].replace('/', '-')}-{state['new_version']}",
        title=f"graft: upgrade {state['dep_name']} {state['old_version']} → {state['new_version']}",
        body=pr_body,
        file_changes=state.get("current_diff"),
    )
    return {"pr_body": pr_body, "pr_url": pr_url, "status": "success"}
