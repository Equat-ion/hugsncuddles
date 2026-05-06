"""
github.py — Create GitHub PRs using GitHub App authentication.

Env vars read (via api.settings):
  GITHUB_APP_ID             — Numeric App ID shown on your GitHub App's settings page.
  GITHUB_APP_PRIVATE_KEY    — Full PEM private key content (newlines as \\n in .env).
                              Generate at: GitHub App → "Generate a private key".
  GITHUB_INSTALLATION_ID    — Installation ID of the App on the target repo.
                              Found in the URL after installing the App:
                              github.com/settings/installations/<ID>

GitHub App setup (one-time):
  1. GitHub → Settings → Developer settings → GitHub Apps → New GitHub App
  2. Set permissions:
       Contents: Read & write   (to push branches)
       Pull requests: Read & write  (to open PRs)
  3. Uncheck "Active webhook" (not needed)
  4. Install the App on your repo → note the Installation ID from the redirect URL.
"""

from __future__ import annotations

import base64

from github import Auth, GithubIntegration
from github.GithubException import GithubException

from api.settings import settings


def _get_github_for_installation():
    """
    Authenticate as the GitHub App Installation and return a Github client.

    The private key may be stored in .env with literal \\n characters.
    We normalise it back to real newlines here.
    """
    private_key: str = settings.github_app_private_key
    # Normalise escaped newlines stored in .env ("\\n" → "\n")
    private_key = private_key.replace("\\n", "\n")

    auth = Auth.AppAuth(
        app_id=int(settings.github_app_id),
        private_key=private_key,
    )
    gi = GithubIntegration(auth=auth)
    return gi.get_github_for_installation(int(settings.github_installation_id))


def create_github_pr(
    repo: str,
    branch: str,
    title: str,
    body: str,
    file_changes: dict[str, str] | None = None,
    base_branch: str = "main",
) -> str:
    """
    Create a GitHub pull request.

    Args:
        repo:         Full repo name, e.g. "owner/my-repo".
        branch:       Name of the new branch to create (e.g. "graft/upgrade-requests-3.0").
        title:        PR title.
        body:         PR body (markdown).
        file_changes: Dict of {relative_file_path: new_file_content} to commit.
                      If None or empty, an empty commit is created as a placeholder.
        base_branch:  Branch to open the PR against (default: "main").

    Returns:
        The HTML URL of the created PR, e.g. "https://github.com/owner/repo/pull/42".

    Raises:
        RuntimeError: On authentication failure or API error.
    """
    try:
        g = _get_github_for_installation()
        gh_repo = g.get_repo(repo)

        # Get the SHA of the base branch tip
        base_ref = gh_repo.get_branch(base_branch)
        base_sha = base_ref.commit.sha

        # Create the new branch
        try:
            gh_repo.create_git_ref(ref=f"refs/heads/{branch}", sha=base_sha)
        except GithubException as exc:
            if exc.status == 422:
                # Branch already exists — reuse it
                pass
            else:
                raise

        # Commit file changes (if any)
        if file_changes:
            _commit_files(gh_repo, branch, file_changes, base_sha, title)

        # Open the PR
        try:
            pr = gh_repo.create_pull(
                title=title,
                body=body,
                head=branch,
                base=base_branch,
                draft=False,
            )
            return pr.html_url
        except GithubException as exc:
            if exc.status == 422 and "already exists" in str(exc.data):
                # PR already open for this branch — find and return it
                for pr in gh_repo.get_pulls(state="open", head=branch):
                    return pr.html_url
            raise

    except GithubException as exc:
        raise RuntimeError(
            f"GitHub API error creating PR on {repo}: {exc.status} {exc.data}"
        ) from exc


def _commit_files(
    gh_repo,
    branch: str,
    file_changes: dict[str, str],
    base_sha: str,
    commit_message: str,
) -> None:
    """
    Create a single commit on `branch` that updates all files in file_changes.

    Uses the Git Data API (blobs + tree + commit) for atomic multi-file commits.
    """
    # 1. Create blobs for each changed file
    blobs = []
    for path, content in file_changes.items():
        blob = gh_repo.create_git_blob(
            content=base64.b64encode(content.encode()).decode(),
            encoding="base64",
        )
        blobs.append(
            {
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": blob.sha,
            }
        )

    # 2. Create a new tree on top of the base tree
    base_commit = gh_repo.get_git_commit(base_sha)
    new_tree = gh_repo.create_git_tree(
        tree=blobs,
        base_tree=base_commit.tree,
    )

    # 3. Create the commit
    new_commit = gh_repo.create_git_commit(
        message=commit_message,
        tree=new_tree,
        parents=[base_commit],
    )

    # 4. Move the branch ref to the new commit
    ref = gh_repo.get_git_ref(f"heads/{branch}")
    ref.edit(sha=new_commit.sha, force=False)
