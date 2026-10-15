"""Tests for Tier 4 Git and PR integration services."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from henchman.git.clients import CommandResult, GitHubCliClient
from henchman.git.github_app import GitHubAppService, GitHubWebhookService
from henchman.git.review import (
    AutofixService,
    PullRequestDiffCache,
    PullRequestReviewer,
    ReviewFinding,
)
from henchman.git.workflow import CommitAssistant


class _StaticGitClient:
    """Minimal git client test double."""

    def __init__(
        self,
        *,
        changed_files: list[str] | None = None,
        staged_diff: str = "",
        working_diff: str = "",
    ) -> None:
        self._changed_files = changed_files or []
        self._staged_diff = staged_diff
        self._working_diff = working_diff

    def changed_files(self, *, staged_only: bool = True) -> tuple[str, ...]:
        del staged_only
        return tuple(self._changed_files)

    def diff(self, *, staged: bool = False) -> str:
        return self._staged_diff if staged else self._working_diff


class _StaticGitHubClient:
    """Minimal GitHub CLI client test double."""

    def __init__(self, diff_text: str = "") -> None:
        self._diff_text = diff_text

    def repo_name_with_owner(self) -> str:
        return "octo/repo"

    def pull_request_diff(self, pr_number: int, *, repo_slug: str | None = None) -> str:
        del pr_number, repo_slug
        return self._diff_text


def test_commit_assistant_generates_docs_message() -> None:
    """Docs-only changes should produce a docs-scoped commit suggestion."""

    assistant = CommitAssistant(
        git_client=_StaticGitClient(changed_files=["README.md", "CHANGELOG.md"]),
    )

    suggestion = assistant.suggest()

    assert suggestion.message == "docs: update readme and changelog"
    assert suggestion.commit_type == "docs"
    assert suggestion.scope is None


def test_pr_diff_cache_reuses_cached_diff_until_refresh(tmp_path: Path) -> None:
    """PR diffs should be cached under the canonical project settings directory."""

    cache = PullRequestDiffCache(project_root=tmp_path)
    fetch_count = 0

    def _fetch() -> str:
        nonlocal fetch_count
        fetch_count += 1
        return f"diff payload {fetch_count}"

    first = cache.get_or_fetch(pr_number=7, repo_slug="octo/repo", fetcher=_fetch)
    second = cache.get_or_fetch(pr_number=7, repo_slug="octo/repo", fetcher=_fetch)
    refreshed = cache.get_or_fetch(
        pr_number=7,
        repo_slug="octo/repo",
        fetcher=_fetch,
        refresh=True,
    )

    assert first == "diff payload 1"
    assert second == "diff payload 1"
    assert refreshed == "diff payload 2"
    assert fetch_count == 2


def test_pull_request_reviewer_flags_general_findings() -> None:
    """General review mode should surface broad exception, TODO, and debug patterns."""

    diff_text = """diff --git a/src/demo.py b/src/demo.py
index 1111111..2222222 100644
--- a/src/demo.py
+++ b/src/demo.py
@@ -0,0 +1,6 @@
+print("debug")
+# TODO: follow up
+try:
+    run()
+except Exception:
+    pass
"""
    reviewer = PullRequestReviewer(
        git_client=_StaticGitClient(working_diff=diff_text),
        github_client=_StaticGitHubClient(),
        diff_cache=PullRequestDiffCache(project_root=Path.cwd()),
    )

    report = reviewer.review(mode="general")
    finding_codes = {finding.code for finding in report.findings}

    assert report.target == "working-tree"
    assert {"debug-statement", "todo-comment", "broad-except", "missing-tests"} <= finding_codes


def test_pull_request_reviewer_flags_security_findings() -> None:
    """Security review mode should surface common risky additions in the diff."""

    diff_text = """diff --git a/src/demo.py b/src/demo.py
index 1111111..2222222 100644
--- a/src/demo.py
+++ b/src/demo.py
@@ -0,0 +1,5 @@
+api_key = "secret-value"
+subprocess.run(command, shell=True)
+config = yaml.load(payload)
+result = eval(user_input)
+requests.get(url)
"""
    reviewer = PullRequestReviewer(
        git_client=_StaticGitClient(working_diff=diff_text),
        github_client=_StaticGitHubClient(),
        diff_cache=PullRequestDiffCache(project_root=Path.cwd()),
    )

    report = reviewer.review(mode="security")
    finding_codes = {finding.code for finding in report.findings}

    assert {
        "hardcoded-secret",
        "subprocess-shell-true",
        "unsafe-yaml-load",
        "dynamic-eval",
        "missing-timeout",
    } <= finding_codes


def test_autofix_service_applies_safe_fixes(tmp_path: Path) -> None:
    """Autofix should remove debug statements and upgrade yaml.load safely."""

    source_file = tmp_path / "src" / "demo.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        'import yaml\n\nprint("debug")\nconfig = yaml.load(payload)\n',
        encoding="utf-8",
    )
    service = AutofixService(project_root=tmp_path)

    report = service.apply_findings(
        [
            ReviewFinding(
                code="debug-statement",
                severity="medium",
                file_path=str(source_file),
                line_number=3,
                message="Remove debug output before shipping.",
                suggestion="Delete the debug statement.",
                excerpt='print("debug")',
                fixable=True,
            ),
            ReviewFinding(
                code="unsafe-yaml-load",
                severity="medium",
                file_path=str(source_file),
                line_number=4,
                message="Use yaml.safe_load for untrusted input.",
                suggestion="Replace yaml.load with yaml.safe_load.",
                excerpt="config = yaml.load(payload)",
                fixable=True,
            ),
        ],
        apply=True,
    )

    assert report.applied_count == 2
    updated = source_file.read_text(encoding="utf-8")
    assert 'print("debug")' not in updated
    assert "yaml.safe_load" in updated


def test_github_app_service_persists_installation_record(tmp_path: Path) -> None:
    """GitHub app setup should persist a reusable local installation record."""

    service = GitHubAppService(project_root=tmp_path)

    record = service.install(
        app_url="https://example.com/apps/henchman/installations/new",
        repo_slug="octo/repo",
        installation_id=42,
        webhook_secret_env="HENCHMAN_GITHUB_WEBHOOK_SECRET",
        open_browser=False,
    )

    assert record.repo_slug == "octo/repo"
    assert record.installation_id == 42
    assert record.metadata_path.exists()
    payload = json.loads(record.metadata_path.read_text(encoding="utf-8"))
    assert payload["app_url"] == "https://example.com/apps/henchman/installations/new"
    assert payload["repo_slug"] == "octo/repo"


def test_github_webhook_service_verifies_signature_and_invalidates_cache(tmp_path: Path) -> None:
    """A valid pull_request webhook should invalidate the cached diff for that PR."""

    cache = PullRequestDiffCache(project_root=tmp_path)
    cache.store(pr_number=7, repo_slug="octo/repo", diff_text="cached diff")
    secret = "top-secret"
    payload = {
        "action": "synchronize",
        "number": 7,
        "repository": {"full_name": "octo/repo"},
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    result = GitHubWebhookService().handle_event(
        event_name="pull_request",
        payload=payload_bytes,
        signature=signature,
        secret=secret,
        diff_cache=cache,
    )

    assert result.signature_valid is True
    assert result.cache_invalidated is True
    assert cache.exists(pr_number=7, repo_slug="octo/repo") is False


def test_github_cli_client_replies_to_review_comment() -> None:
    """Replying to a review comment should use the GitHub CLI API surface safely."""

    captured: list[list[str]] = []

    def _runner(argv: list[str], cwd: Path | None = None) -> CommandResult:
        del cwd
        captured.append(argv)
        return CommandResult(
            argv=tuple(argv),
            returncode=0,
            stdout='{"html_url": "https://github.com/octo/repo/pull/7#discussion_r11"}',
            stderr="",
        )

    client = GitHubCliClient(runner=_runner)

    reply_url = client.reply_to_review_comment(
        pr_number=7,
        comment_id=11,
        body="Thanks, fixed.",
        repo_slug="octo/repo",
    )

    assert reply_url.endswith("#discussion_r11")
    assert captured == [
        [
            "gh",
            "api",
            "--method",
            "POST",
            "repos/octo/repo/pulls/7/comments/11/replies",
            "-f",
            "body=Thanks, fixed.",
        ]
    ]
