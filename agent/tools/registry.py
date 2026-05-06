"""
registry.py — Fetch dependency diffs and migration guides from PyPI + GitHub.

Env vars read (via api.settings):
  GITHUB_TOKEN  — GitHub Personal Access Token (classic), public_repo scope.
                  Optional but strongly recommended to avoid 60 req/hr rate limit.
                  Generate at: GitHub → Settings → Developer settings → PATs (classic)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from api.settings import settings

PYPI_API = "https://pypi.org/pypi/{pkg}/json"
GH_RELEASES_API = "https://api.github.com/repos/{owner}/{repo}/releases"
GH_RAW = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
CHANGELOG_CANDIDATES = ["CHANGELOG.md", "CHANGELOG.rst", "HISTORY.md", "HISTORY.rst", "CHANGES.md"]


@dataclass
class DepSource:
    source: str
    changelog: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _gh_headers() -> dict[str, str]:
    """Return GitHub API headers, optionally authenticated."""
    token = getattr(settings, "github_token", None)
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _pypi_info(dep: str) -> dict[str, Any]:
    """Fetch package metadata from PyPI JSON API."""
    resp = httpx.get(PYPI_API.format(pkg=dep), timeout=15)
    resp.raise_for_status()
    return resp.json()


def _extract_github_repo(info: dict[str, Any]) -> tuple[str, str] | None:
    """Extract (owner, repo) from PyPI project_urls."""
    urls: dict[str, str] = info.get("project_urls") or {}
    for url in urls.values():
        m = re.search(r"github\.com/([^/]+)/([^/\s#]+)", url or "")
        if m:
            owner, repo = m.group(1), m.group(2).rstrip(".git")
            return owner, repo
    # Fallback: check homepage
    homepage = info.get("home_page") or ""
    m = re.search(r"github\.com/([^/]+)/([^/\s#]+)", homepage)
    if m:
        return m.group(1), m.group(2).rstrip(".git")
    return None


def _version_tuple(v: str) -> tuple[int, ...]:
    """Convert '1.2.3' → (1, 2, 3) for ordering. Non-numeric parts become 0."""
    parts = []
    for segment in re.split(r"[.\-]", v):
        try:
            parts.append(int(segment))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _releases_between(owner: str, repo: str, old_v: str, new_v: str) -> list[dict]:
    """Return GitHub releases whose tag falls between old_v (exclusive) and new_v (inclusive)."""
    resp = httpx.get(
        GH_RELEASES_API.format(owner=owner, repo=repo),
        headers=_gh_headers(),
        params={"per_page": 100},
        timeout=15,
    )
    resp.raise_for_status()
    releases = resp.json()

    old_t = _version_tuple(old_v)
    new_t = _version_tuple(new_v)

    matched = []
    for r in releases:
        tag = r.get("tag_name", "").lstrip("v")
        t = _version_tuple(tag)
        if old_t < t <= new_t:
            matched.append(r)
    return sorted(matched, key=lambda r: _version_tuple(r.get("tag_name", "").lstrip("v")))


def _fetch_changelog_file(owner: str, repo: str) -> str | None:
    """Try to fetch a known changelog file from the default branch."""
    for path in CHANGELOG_CANDIDATES:
        for branch in ("main", "master"):
            url = GH_RAW.format(owner=owner, repo=repo, branch=branch, path=path)
            try:
                resp = httpx.get(url, headers=_gh_headers(), timeout=10)
                if resp.status_code == 200:
                    return resp.text
            except httpx.HTTPError:
                continue
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_dep_source(dep: str, version: str) -> str:
    """Return the PyPI source URL (sdist tarball) for a given package+version."""
    info = _pypi_info(dep)
    releases = info.get("releases", {}).get(version, [])
    # Prefer sdist over wheel
    for artifact in releases:
        if artifact.get("packagetype") == "sdist":
            return artifact["url"]
    # Fallback: first artifact
    if releases:
        return releases[0]["url"]
    raise ValueError(f"No release artifacts found for {dep}=={version}")


def fetch_dep_diff(dep: str, old_v: str, new_v: str) -> str:
    """
    Return a human-readable diff string of release notes between old_v and new_v.

    Strategy:
    1. Look up GitHub repo via PyPI metadata
    2. Fetch GitHub release bodies between the two versions
    3. If no releases found, fall back to a raw CHANGELOG excerpt
    """
    info = _pypi_info(dep)["info"]
    coords = _extract_github_repo(info)

    if not coords:
        return f"[registry] Could not resolve GitHub repo for '{dep}'. No diff available."

    owner, repo = coords

    try:
        releases = _releases_between(owner, repo, old_v, new_v)
    except httpx.HTTPError as exc:
        return f"[registry] GitHub API error fetching releases for {dep}: {exc}"

    if releases:
        parts = [f"# {dep}: {old_v} → {new_v}\n"]
        for r in releases:
            tag = r.get("tag_name", "?")
            body = (r.get("body") or "*(no release notes)*").strip()
            parts.append(f"## {tag}\n\n{body}\n")
        return "\n".join(parts)

    # Fallback: raw changelog file (truncated to 4 000 chars)
    changelog = _fetch_changelog_file(owner, repo)
    if changelog:
        return (
            f"# {dep}: {old_v} → {new_v}\n\n"
            f"*(No GitHub releases found — raw CHANGELOG below)*\n\n"
            + changelog[:4000]
        )

    return (
        f"[registry] No release notes or changelog found for {dep} "
        f"between {old_v} and {new_v} in {owner}/{repo}."
    )


def fetch_migration_guide(dep: str, old_v: str, new_v: str) -> str:
    """
    Return a migration guide string.

    Strategy:
    1. Look for CHANGELOG / MIGRATION file in the GitHub repo
    2. Fall back to release notes from fetch_dep_diff
    """
    info = _pypi_info(dep)["info"]
    coords = _extract_github_repo(info)

    if not coords:
        return fetch_dep_diff(dep, old_v, new_v)

    owner, repo = coords
    changelog = _fetch_changelog_file(owner, repo)

    if changelog:
        # Heuristic: try to extract section between old_v and new_v
        section = _extract_section(changelog, old_v, new_v)
        if section:
            return f"# Migration guide: {dep} {old_v} → {new_v}\n\n{section}"
        # Return full changelog (capped) if section extraction fails
        return (
            f"# Migration guide: {dep} {old_v} → {new_v}\n\n"
            f"*(Full CHANGELOG — relevant sections for {old_v}→{new_v} below)*\n\n"
            + changelog[:6000]
        )

    # Final fallback: reuse the diff
    return fetch_dep_diff(dep, old_v, new_v)


def _extract_section(changelog: str, old_v: str, new_v: str) -> str | None:
    """
    Attempt to slice a CHANGELOG between headings that match new_v and old_v.
    Returns None if heuristic fails.
    """
    # Match headings like ## 1.2.3, ## v1.2.3, # [1.2.3], etc.
    heading_re = re.compile(
        r"^#{1,3}\s*(?:v|version\s*)?(\d+\.\d+[\.\d]*)",
        re.MULTILINE | re.IGNORECASE,
    )
    matches = list(heading_re.finditer(changelog))
    if not matches:
        return None

    new_t = _version_tuple(new_v)
    old_t = _version_tuple(old_v)

    start_idx: int | None = None
    end_idx: int | None = None

    for m in matches:
        t = _version_tuple(m.group(1))
        if t == new_t and start_idx is None:
            start_idx = m.start()
        if t == old_t and start_idx is not None:
            end_idx = m.start()
            break

    if start_idx is None:
        return None

    return changelog[start_idx:end_idx].strip() if end_idx else changelog[start_idx:start_idx + 4000].strip()
