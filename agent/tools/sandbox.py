"""
sandbox.py — Run pytest inside an e2b cloud sandbox.

Env vars read (via api.settings):
  E2B_API_KEY  — API key from https://e2b.dev/dashboard → API Keys
                 Free tier: 100 sandbox-hours/month.
                 Set E2B_API_KEY in your .env file.

How it works:
  1. Zip the local repo (excluding .git, __pycache__, .venv)
  2. Spin up an e2b Sandbox
  3. Upload the zip and extract it
  4. Install the project dependencies inside the sandbox
  5. Install pytest + pytest-json-report inside the sandbox
  6. Run pytest with --json-report to get structured output
  7. Parse the JSON report into SandboxResult
  8. Close the sandbox
"""

from __future__ import annotations

import io
import json
import os
import time
import zipfile
from pathlib import Path

from e2b_code_interpreter import Sandbox

from agent.state import SandboxResult
from api.settings import settings

# Directories to exclude when zipping the repo
_EXCLUDE_DIRS = {".git", "__pycache__", ".venv", ".mypy_cache", ".pytest_cache", "node_modules"}
_EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def _zip_repo(repo_path: str) -> bytes:
    """Return an in-memory zip of the repo, excluding noise directories."""
    root = Path(repo_path).resolve()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            # Skip excluded directories anywhere in the path
            if any(part in _EXCLUDE_DIRS for part in path.parts):
                continue
            if path.suffix in _EXCLUDE_SUFFIXES:
                continue
            if path.is_file():
                arcname = path.relative_to(root)
                zf.write(path, arcname)
    return buf.getvalue()


def _parse_json_report(report_json: str) -> SandboxResult:
    """Parse pytest-json-report output into SandboxResult."""
    try:
        report = json.loads(report_json)
    except json.JSONDecodeError:
        # Couldn't parse — treat as total failure
        return SandboxResult(
            passed=False,
            total=0,
            failed_names=[],
            errors=["Failed to parse pytest JSON report"],
            stdout=report_json[:2000],
            duration_ms=0,
        )

    summary = report.get("summary", {})
    total = summary.get("total", 0)
    failed = summary.get("failed", 0) + summary.get("error", 0)
    passed_count = summary.get("passed", 0)
    duration_ms = int(report.get("duration", 0) * 1000)

    failed_names: list[str] = []
    errors: list[str] = []

    for test in report.get("tests", []):
        if test.get("outcome") in ("failed", "error"):
            failed_names.append(test.get("nodeid", "unknown"))
            longrepr = test.get("call", {}).get("longrepr") or test.get("setup", {}).get("longrepr", "")
            if longrepr:
                errors.append(f"{test.get('nodeid')}: {longrepr[:500]}")

    all_passed = failed == 0 and total > 0

    return SandboxResult(
        passed=all_passed,
        total=total,
        failed_names=failed_names,
        errors=errors,
        stdout=f"{passed_count}/{total} passed",
        duration_ms=duration_ms,
    )


def run_tests(repo_path: str, test_filter: str | None = None) -> SandboxResult:
    """
    Zip the repo at repo_path, upload it to an e2b sandbox, run pytest,
    and return a SandboxResult.

    Args:
        repo_path: Absolute path to the local repo root.
        test_filter: Optional pytest -k filter expression (e.g. "test_foo or test_bar").

    Returns:
        SandboxResult with pass/fail counts and error details.

    Raises:
        RuntimeError: If the sandbox cannot be created or the upload fails.
    """
    api_key = getattr(settings, "e2b_api_key", None) or os.environ.get("E2B_API_KEY")
    if not api_key:
        raise RuntimeError(
            "E2B_API_KEY is not set. "
            "Get your key at https://e2b.dev/dashboard and add E2B_API_KEY to .env"
        )

    start = time.time()

    # 1. Zip repo
    zip_bytes = _zip_repo(repo_path)

    with Sandbox(api_key=api_key) as sandbox:
        # 2. Upload zip
        sandbox.files.write("/home/user/repo.zip", zip_bytes)

        # 3. Extract
        sandbox.run_code(
            "import subprocess; subprocess.run(['unzip', '-q', '/home/user/repo.zip', '-d', '/home/user/repo'], check=True)",
            language="python",
        )

        # 4. Install project deps
        setup_result = sandbox.run_code(
            """
import subprocess, sys
result = subprocess.run(
    [sys.executable, '-m', 'pip', 'install', '-e', '/home/user/repo', '--quiet'],
    capture_output=True, text=True
)
print(result.stdout[-500:] if result.stdout else '')
print(result.stderr[-500:] if result.stderr else '')
""",
            language="python",
        )

        # 5. Install pytest + json-report plugin
        sandbox.run_code(
            """
import subprocess, sys
subprocess.run(
    [sys.executable, '-m', 'pip', 'install', 'pytest', 'pytest-json-report', '--quiet'],
    check=True
)
""",
            language="python",
        )

        # 6. Build pytest command
        pytest_cmd = [
            "sys.executable, '-m', 'pytest'",
            "'/home/user/repo'",
            "'--json-report'",
            "'--json-report-file=/tmp/report.json'",
            "'-q', '--tb=short'",
        ]
        if test_filter:
            pytest_cmd.append(f"'-k', {repr(test_filter)}")

        run_result = sandbox.run_code(
            f"""
import subprocess, sys
result = subprocess.run(
    [{', '.join(pytest_cmd)}],
    capture_output=True, text=True, cwd='/home/user/repo'
)
print(result.stdout)
print(result.stderr)
""",
            language="python",
        )

        # 7. Read JSON report
        report_result = sandbox.run_code(
            """
try:
    with open('/tmp/report.json') as f:
        print(f.read())
except FileNotFoundError:
    print('{}')
""",
            language="python",
        )

    report_json = "\n".join(report_result.logs.stdout).strip()
    result = _parse_json_report(report_json)

    # Patch duration if JSON report had 0 (e.g. parse error)
    if result["duration_ms"] == 0:
        result = SandboxResult(**{**result, "duration_ms": int((time.time() - start) * 1000)})

    return result
