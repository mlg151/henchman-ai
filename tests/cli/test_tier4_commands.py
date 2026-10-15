"""Tests for Tier 4 Git and PR CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from henchman.cli.app import cli
from henchman.cli.commands.git_command import (
    create_branch_command,
    create_commit_command,
    create_commit_push_pr_command,
)
from henchman.cli.commands.pull_request_command import (
    create_autofix_pr_command,
    create_install_github_app_command,
    create_pr_comments_command,
    create_review_command,
    create_security_review_command,
)
from henchman.git.github_app import GitHubAppInstallRecord
from henchman.git.review import AutofixReport, CommentDraft, CommentReplyResult, ReviewReport
from henchman.git.workflow import (
    BranchInfo,
    BranchOperation,
    CommitSuggestion,
    PullRequestWorkflowResult,
)


def test_commit_command_renders_suggestion() -> None:
    """`commit` should render the generated commit message."""

    class FakeCommitAssistant:
        def __init__(self, project_root: Path | None = None) -> None:
            del project_root

        def suggest(self, *, staged_only: bool = True) -> CommitSuggestion:
            del staged_only
            return CommitSuggestion(
                message="feat(cli): add review command",
                commit_type="feat",
                scope="cli",
                summary="add review command",
                files=("src/henchman/cli/commands/pull_request_command.py",),
            )

    runner = CliRunner()
    result = runner.invoke(create_commit_command(commit_assistant_factory=FakeCommitAssistant), [])

    assert result.exit_code == 0
    assert "feat(cli): add review command" in result.output


def test_branch_command_supports_list_create_and_switch() -> None:
    """`branch` should expose list, create, and switch operations."""

    class FakeBranchManager:
        def __init__(self, project_root: Path | None = None) -> None:
            del project_root

        def list(self) -> tuple[BranchInfo, ...]:
            return (
                BranchInfo(name="main", is_current=True),
                BranchInfo(name="feature/tier4", is_current=False),
            )

        def create(self, name: str, *, switch: bool = False, start_point: str | None = None) -> BranchOperation:
            del switch, start_point
            return BranchOperation(action="create", branch=name, current_branch=name)

        def switch(self, name: str) -> BranchOperation:
            return BranchOperation(action="switch", branch=name, current_branch=name)

    command = create_branch_command(branch_manager_factory=FakeBranchManager)
    runner = CliRunner()

    list_result = runner.invoke(command, ["list"])
    create_result = runner.invoke(command, ["create", "feature/tier4"])
    switch_result = runner.invoke(command, ["switch", "main"])

    assert list_result.exit_code == 0
    assert "* main" in list_result.output
    assert "feature/tier4" in list_result.output
    assert create_result.exit_code == 0
    assert "Created branch feature/tier4" in create_result.output
    assert switch_result.exit_code == 0
    assert "Switched to branch main" in switch_result.output


def test_commit_push_pr_command_runs_workflow() -> None:
    """`commit-push-pr` should render the created PR URL."""

    class FakeWorkflow:
        def __init__(self, project_root: Path | None = None) -> None:
            del project_root

        def run(
            self,
            *,
            message: str | None = None,
            title: str | None = None,
            body: str | None = None,
            stage_all: bool = False,
            fill: bool = False,
            draft: bool = False,
        ) -> PullRequestWorkflowResult:
            del message, title, body, stage_all, fill, draft
            return PullRequestWorkflowResult(
                commit_message="feat(cli): add review command",
                branch="feature/tier4",
                pull_request_url="https://github.com/octo/repo/pull/7",
            )

    runner = CliRunner()
    result = runner.invoke(
        create_commit_push_pr_command(workflow_factory=FakeWorkflow),
        ["--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["pull_request_url"] == "https://github.com/octo/repo/pull/7"


def test_review_command_renders_report() -> None:
    """`review` should render findings from the shared review service."""

    class FakeReviewer:
        def __init__(self, project_root: Path | None = None) -> None:
            del project_root

        def review(self, *, pr_number: int | None = None, mode: str = "general", refresh: bool = False) -> ReviewReport:
            del pr_number, mode, refresh
            return ReviewReport(
                mode="general",
                target="working-tree",
                summary="2 findings",
                findings=(),
            )

    runner = CliRunner()
    result = runner.invoke(create_review_command(reviewer_factory=FakeReviewer), [])

    assert result.exit_code == 0
    assert "2 findings" in result.output


def test_security_review_command_uses_security_mode() -> None:
    """`security-review` should request the security review mode from the service."""

    captured_modes: list[str] = []

    class FakeReviewer:
        def __init__(self, project_root: Path | None = None) -> None:
            del project_root

        def review(self, *, pr_number: int | None = None, mode: str = "general", refresh: bool = False) -> ReviewReport:
            del pr_number, refresh
            captured_modes.append(mode)
            return ReviewReport(
                mode=mode,
                target="working-tree",
                summary="security findings",
                findings=(),
            )

    runner = CliRunner()
    result = runner.invoke(create_security_review_command(reviewer_factory=FakeReviewer), [])

    assert result.exit_code == 0
    assert captured_modes == ["security"]


def test_pr_comments_command_generates_and_responds() -> None:
    """`pr_comments` should draft and send replies through the shared service."""

    sent: list[tuple[int, int, str]] = []

    class FakeCommentManager:
        def __init__(self, project_root: Path | None = None) -> None:
            del project_root

        def generate(self, *, pr_number: int) -> tuple[CommentDraft, ...]:
            del pr_number
            return (
                CommentDraft(
                    comment_id=11,
                    original_body="Can you add tests?",
                    draft_reply="Absolutely - I'll add focused test coverage.",
                    path="src/demo.py",
                ),
            )

        def respond(self, *, pr_number: int, comment_id: int, body: str) -> CommentReplyResult:
            sent.append((pr_number, comment_id, body))
            return CommentReplyResult(
                pr_number=pr_number,
                comment_id=comment_id,
                body=body,
                reply_url="https://github.com/octo/repo/pull/7#discussion_r11",
            )

    command = create_pr_comments_command(comment_manager_factory=FakeCommentManager)
    runner = CliRunner()

    generate_result = runner.invoke(command, ["generate", "--pr", "7"])
    respond_result = runner.invoke(
        command,
        ["respond", "--pr", "7", "--comment-id", "11", "--body", "Done."],
    )

    assert generate_result.exit_code == 0
    assert "I'll add focused test coverage" in generate_result.output
    assert respond_result.exit_code == 0
    assert sent == [(7, 11, "Done.")]


def test_autofix_pr_command_renders_report() -> None:
    """`autofix-pr` should render applied and skipped fix counts."""

    class FakeAutofixService:
        def __init__(self, project_root: Path | None = None) -> None:
            del project_root

        def autofix(
            self,
            *,
            pr_number: int | None = None,
            refresh: bool = False,
            apply: bool = False,
        ) -> AutofixReport:
            del pr_number, refresh, apply
            return AutofixReport(
                applied_count=1,
                skipped_count=2,
                changes=(),
            )

    runner = CliRunner()
    result = runner.invoke(
        create_autofix_pr_command(autofix_service_factory=FakeAutofixService),
        [],
    )

    assert result.exit_code == 0
    assert "Applied fixes: 1" in result.output
    assert "Skipped fixes: 2" in result.output


def test_install_github_app_command_renders_record(tmp_path: Path) -> None:
    """`install-github-app` should render persisted setup metadata."""

    metadata_path = tmp_path / ".henchman" / "github" / "app_installation.json"

    class FakeGitHubAppService:
        def __init__(self, project_root: Path | None = None) -> None:
            del project_root

        def install(
            self,
            *,
            app_url: str,
            repo_slug: str | None = None,
            installation_id: int | None = None,
            webhook_secret_env: str = "HENCHMAN_GITHUB_WEBHOOK_SECRET",
            open_browser: bool = False,
        ) -> GitHubAppInstallRecord:
            del app_url, open_browser
            return GitHubAppInstallRecord(
                app_url="https://example.com/apps/henchman/installations/new",
                repo_slug=repo_slug or "octo/repo",
                installation_id=installation_id,
                webhook_secret_env=webhook_secret_env,
                metadata_path=metadata_path,
            )

    runner = CliRunner()
    result = runner.invoke(
        create_install_github_app_command(github_app_service_factory=FakeGitHubAppService),
        ["--app-url", "https://example.com/apps/henchman/installations/new", "--repo", "octo/repo"],
    )

    assert result.exit_code == 0
    assert "octo/repo" in result.output
    assert str(metadata_path) in result.output


def test_root_cli_registers_tier4_commands() -> None:
    """The root CLI should expose the Tier 4 command surfaces."""

    expected = {
        "commit",
        "branch",
        "review",
        "pr_comments",
        "commit-push-pr",
        "autofix-pr",
        "security-review",
        "install-github-app",
    }

    assert expected <= set(cli.commands)
