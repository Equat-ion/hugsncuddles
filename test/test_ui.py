#!/usr/bin/env python3
"""
test/test_ui.py — Graft backend integration test TUI.

Run with:  python test/test_ui.py
           (or: uv run python test/test_ui.py)

Tests three backends:
  [1] Registry  — fetch dep diff + migration guide from PyPI / GitHub
  [2] Sandbox   — run a trivial pytest inside an e2b cloud sandbox
  [3] GitHub    — authenticate as the GitHub App and fetch the installation info

Press Q or Ctrl+C to quit.
"""

from __future__ import annotations

import asyncio
import sys
import textwrap
import traceback
from pathlib import Path

# Make sure the repo root is on sys.path regardless of cwd
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Rule,
    Static,
)

# ── colour palette (used in CSS) ────────────────────────────────────────────
CSS = """
Screen {
    background: $surface;
}

#title {
    text-align: center;
    color: $accent;
    text-style: bold;
    padding: 1 0;
}

#inputs {
    padding: 0 2;
    height: auto;
}

.row {
    height: 3;
    margin-bottom: 1;
}

.label {
    width: 18;
    content-align: right middle;
    color: $text-muted;
    padding-right: 1;
}

Input {
    width: 1fr;
}

#buttons {
    padding: 1 2;
    height: auto;
    align: center middle;
}

Button {
    margin: 0 1;
    min-width: 20;
}

#btn-registry  { background: #1a6b9a; }
#btn-sandbox   { background: #1a7a4a; }
#btn-github    { background: #7a3a8a; }
#btn-clear     { background: $surface-darken-2; }

#btn-registry:hover  { background: #2080bb; }
#btn-sandbox:hover   { background: #20944a; }
#btn-github:hover    { background: #9340aa; }

#log-container {
    border: round $accent 50%;
    margin: 0 2 1 2;
    height: 1fr;
    padding: 0 1;
}

#log {
    height: 1fr;
}

#status-bar {
    height: 1;
    background: $primary-darken-3;
    padding: 0 2;
    color: $text-muted;
}
"""


class GraftTestUI(App):
    """Simple one-screen TUI for testing Graft's three backends."""

    CSS = CSS
    TITLE = "Graft — Backend Integration Tester"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+l", "clear_log", "Clear"),
    ]

    # reactive flag — disables buttons while a test is running
    _busy: reactive[bool] = reactive(False)

    # ── layout ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        yield Static("⚡  Graft Backend Tester", id="title")

        with Vertical(id="inputs"):
            with Horizontal(classes="row"):
                yield Label("Package name:", classes="label")
                yield Input(value="requests", id="inp-dep", placeholder="e.g. requests")
            with Horizontal(classes="row"):
                yield Label("Old version:", classes="label")
                yield Input(value="2.28.0", id="inp-old", placeholder="e.g. 2.28.0")
            with Horizontal(classes="row"):
                yield Label("New version:", classes="label")
                yield Input(value="2.32.0", id="inp-new", placeholder="e.g. 2.32.0")
            with Horizontal(classes="row"):
                yield Label("Repo path:", classes="label")
                yield Input(value=str(ROOT), id="inp-repo", placeholder="abs path to a local repo")
            with Horizontal(classes="row"):
                yield Label("GitHub repo:", classes="label")
                yield Input(value="", id="inp-gh-repo", placeholder="owner/repo  (for GitHub test)")

        with Horizontal(id="buttons"):
            yield Button("① Registry", id="btn-registry", variant="primary")
            yield Button("② Sandbox", id="btn-sandbox", variant="success")
            yield Button("③ GitHub App", id="btn-github", variant="warning")
            yield Button("✕ Clear", id="btn-clear", variant="default")

        with ScrollableContainer(id="log-container"):
            yield RichLog(id="log", highlight=True, markup=True)

        yield Static("Ready — pick a test above.", id="status-bar")
        yield Footer()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _log(self, *lines: str) -> None:
        log = self.query_one("#log", RichLog)
        for line in lines:
            log.write(line)

    def _status(self, msg: str) -> None:
        self.query_one("#status-bar", Static).update(msg)

    def _inputs(self) -> dict[str, str]:
        return {
            "dep":     self.query_one("#inp-dep",     Input).value.strip(),
            "old_v":   self.query_one("#inp-old",     Input).value.strip(),
            "new_v":   self.query_one("#inp-new",     Input).value.strip(),
            "repo":    self.query_one("#inp-repo",    Input).value.strip(),
            "gh_repo": self.query_one("#inp-gh-repo", Input).value.strip(),
        }

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for btn_id in ("btn-registry", "btn-sandbox", "btn-github"):
            self.query_one(f"#{btn_id}", Button).disabled = busy

    # ── button handlers ───────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-registry")
    def run_registry(self) -> None:
        if not self._busy:
            self._run_registry_test()

    @on(Button.Pressed, "#btn-sandbox")
    def run_sandbox(self) -> None:
        if not self._busy:
            self._run_sandbox_test()

    @on(Button.Pressed, "#btn-github")
    def run_github(self) -> None:
        if not self._busy:
            self._run_github_test()

    @on(Button.Pressed, "#btn-clear")
    def action_clear_log(self) -> None:
        self.query_one("#log", Log).clear()
        self._status("Log cleared.")

    # ── workers (run in background thread so TUI stays responsive) ────────────

    @work(thread=True)
    def _run_registry_test(self) -> None:
        inp = self._inputs()
        dep, old_v, new_v = inp["dep"], inp["old_v"], inp["new_v"]

        self._set_busy(True)
        self._log(
            "",
            f"[bold cyan]══ REGISTRY TEST ══[/bold cyan]",
            f"  Package : [yellow]{dep}[/yellow]",
            f"  Versions: [yellow]{old_v}[/yellow] → [yellow]{new_v}[/yellow]",
        )
        self._status(f"Registry: fetching diff for {dep} {old_v}→{new_v} …")

        try:
            from agent.tools.registry import fetch_dep_diff, fetch_migration_guide

            self._log("  ↳ fetch_dep_diff() …")
            diff = fetch_dep_diff(dep, old_v, new_v)
            preview = "\n".join(
                "    " + ln for ln in diff.splitlines()[:30]
            )
            self._log(f"  [green]✓ diff ({len(diff)} chars):[/green]")
            self._log(preview)
            if diff.count("\n") > 30:
                self._log("    … (truncated)")

            self._log("")
            self._log("  ↳ fetch_migration_guide() …")
            guide = fetch_migration_guide(dep, old_v, new_v)
            guide_preview = "\n".join(
                "    " + ln for ln in guide.splitlines()[:20]
            )
            self._log(f"  [green]✓ guide ({len(guide)} chars):[/green]")
            self._log(guide_preview)

            self._log("[bold green]  REGISTRY PASS ✓[/bold green]")
            self._status("Registry: PASS ✓")

        except Exception:
            tb = traceback.format_exc()
            self._log("[bold red]  REGISTRY FAIL ✗[/bold red]")
            for ln in tb.splitlines():
                self._log(f"  [red]{ln}[/red]")
            self._status("Registry: FAIL ✗ — see log")
        finally:
            self._set_busy(False)

    @work(thread=True)
    def _run_sandbox_test(self) -> None:
        inp = self._inputs()
        repo = inp["repo"]

        self._set_busy(True)
        self._log(
            "",
            "[bold green]══ SANDBOX TEST (e2b) ══[/bold green]",
            f"  Repo path: [yellow]{repo}[/yellow]",
            "  (Uploads repo, installs deps, runs pytest — may take 30–60 s)",
        )
        self._status("Sandbox: spinning up e2b cloud VM …")

        try:
            from agent.tools.sandbox import run_tests

            self._log("  ↳ run_tests() …")
            result = run_tests(repo, test_filter=None)

            status_icon = "[green]✓ PASS[/green]" if result["passed"] else "[red]✗ FAIL[/red]"
            self._log(f"  {status_icon}")
            self._log(f"    total      : {result['total']}")
            self._log(f"    stdout     : {result['stdout']}")
            self._log(f"    duration   : {result['duration_ms']} ms")

            if result["failed_names"]:
                self._log("    failed tests:")
                for name in result["failed_names"]:
                    self._log(f"      [red]• {name}[/red]")
            if result["errors"]:
                self._log("    errors:")
                for err in result["errors"][:5]:
                    self._log(f"      [red]{err[:120]}[/red]")

            label = "PASS" if result["passed"] else "FAIL"
            self._log(f"[bold green]  SANDBOX {label}[/bold green]" if result["passed"] else f"[bold yellow]  SANDBOX {label} (tests ran, some failed)[/bold yellow]")
            self._status(f"Sandbox: {label} — {result['total']} tests in {result['duration_ms']} ms")

        except Exception:
            tb = traceback.format_exc()
            self._log("[bold red]  SANDBOX FAIL ✗[/bold red]")
            for ln in tb.splitlines():
                self._log(f"  [red]{ln}[/red]")
            self._status("Sandbox: FAIL ✗ — see log")
        finally:
            self._set_busy(False)

    @work(thread=True)
    def _run_github_test(self) -> None:
        inp = self._inputs()
        gh_repo = inp["gh_repo"]

        self._set_busy(True)
        self._log(
            "",
            "[bold magenta]══ GITHUB APP TEST ══[/bold magenta]",
        )
        self._status("GitHub: authenticating as App …")

        try:
            from api.settings import settings
            from github import Auth, GithubIntegration

            private_key = settings.github_app_private_key.replace("\\n", "\n")
            auth = Auth.AppAuth(
                app_id=int(settings.github_app_id),
                private_key=private_key,
            )
            gi = GithubIntegration(auth=auth)

            self._log(f"  App ID            : [yellow]{settings.github_app_id}[/yellow]")
            self._log(f"  Installation ID   : [yellow]{settings.github_installation_id}[/yellow]")
            self._log("  ↳ get_app() …")

            app = gi.get_app()
            self._log(f"  [green]✓ App name        : {app.name}[/green]")
            self._log(f"  [green]✓ App slug        : {app.slug}[/green]")

            self._log("  ↳ get_installation() …")
            installation = gi.get_installation(int(settings.github_installation_id))
            self._log(f"  [green]✓ Installation ID : {installation.id}[/green]")
            self._log(f"  [green]✓ Account         : {installation.account.login}[/green]")

            if gh_repo:
                self._log(f"  ↳ get_github_for_installation() + get_repo({gh_repo!r}) …")
                g = gi.get_github_for_installation(int(settings.github_installation_id))
                repo = g.get_repo(gh_repo)
                self._log(f"  [green]✓ Repo full name  : {repo.full_name}[/green]")
                self._log(f"  [green]✓ Default branch  : {repo.default_branch}[/green]")
                self._log(f"  [green]✓ Open PRs        : {repo.get_pulls(state='open').totalCount}[/green]")
            else:
                self._log("  [dim](No GitHub repo specified — skipping repo access test)[/dim]")

            self._log("[bold green]  GITHUB PASS ✓[/bold green]")
            self._status("GitHub App: PASS ✓")

        except Exception:
            tb = traceback.format_exc()
            self._log("[bold red]  GITHUB FAIL ✗[/bold red]")
            for ln in tb.splitlines():
                self._log(f"  [red]{ln}[/red]")
            self._status("GitHub App: FAIL ✗ — see log")
        finally:
            self._set_busy(False)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    GraftTestUI().run()
