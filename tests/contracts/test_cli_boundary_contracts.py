"""Contract tests for CLI-facing service boundaries and protocols."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from henchman.agents.delegation import AgentLoopRunner
from henchman.agents.orchestrator_types import AgentLoopParams
from henchman.cli.commands.git_command import (
    _BranchManagerProtocol,
    _CommitAssistantProtocol,
    _WorkflowProtocol,
)
from henchman.cli.commands.pull_request_command import (
    _AutofixServiceProtocol,
    _CommentManagerProtocol,
    _GitHubAppServiceProtocol,
    _ReviewerProtocol,
)
from henchman.cli.textual_widgets import ToolCallProtocol
from henchman.core.events import AgentEvent, EventType
from henchman.git.clients import CommandResult, PullRequestComment
from henchman.git.github_app import GitHubAppInstallRecord
from henchman.git.review import (
    AutofixChange,
    AutofixReport,
    CommentDraft,
    CommentReplyResult,
    ReviewFinding,
    ReviewReport,
)
from henchman.git.workflow import (
    BranchInfo,
    BranchOperation,
    CommitSuggestion,
    PullRequestWorkflowResult,
)
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


def _accept_commit_assistant(service: _CommitAssistantProtocol) -> _CommitAssistantProtocol:
    """Type-level helper for the commit-assistant contract."""
    return service


def _accept_branch_manager(service: _BranchManagerProtocol) -> _BranchManagerProtocol:
    """Type-level helper for the branch-manager contract."""
    return service


def _accept_workflow(service: _WorkflowProtocol) -> _WorkflowProtocol:
    """Type-level helper for the workflow contract."""
    return service


def _accept_reviewer(service: _ReviewerProtocol) -> _ReviewerProtocol:
    """Type-level helper for the reviewer contract."""
    return service


def _accept_comment_manager(service: _CommentManagerProtocol) -> _CommentManagerProtocol:
    """Type-level helper for the comment-manager contract."""
    return service


def _accept_autofix_service(service: _AutofixServiceProtocol) -> _AutofixServiceProtocol:
    """Type-level helper for the autofix-service contract."""
    return service


def _accept_github_app_service(service: _GitHubAppServiceProtocol) -> _GitHubAppServiceProtocol:
    """Type-level helper for the GitHub App service contract."""
    return service


def _accept_tool_call(tool_call: ToolCallProtocol) -> ToolCallProtocol:
    """Type-level helper for the textual tool-call contract."""
    return tool_call


def _accept_agent_loop_runner(runner: AgentLoopRunner) -> AgentLoopRunner:
    """Type-level helper for the orchestrator loop-runner contract."""
    return runner


class _CommitAssistantDouble:
    """Double for the commit-assistant protocol."""

    def suggest(self, *, staged_only: bool = True) -> CommitSuggestion:
        return CommitSuggestion(
            message="feat(cli): add contract checks",
            commit_type="feat",
            scope="cli" if staged_only else None,
            summary="add contract checks",
            files=("src/henchman/testing/contract.py", "tests/contracts/test_cli_boundary_contracts.py"),
        )


class _BranchManagerDouble:
    """Double for the branch-manager protocol."""

    def list(self) -> tuple[BranchInfo, ...]:
        return (BranchInfo(name="main", is_current=True),)

    def create(
        self,
        name: str,
        *,
        switch: bool = False,
        start_point: str | None = None,
    ) -> BranchOperation:
        del switch, start_point
        return BranchOperation(action="create", branch=name, current_branch=name)

    def switch(self, name: str) -> BranchOperation:
        return BranchOperation(action="switch", branch=name, current_branch=name)


class _WorkflowDouble:
    """Double for the commit/push/PR workflow protocol."""

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
        del title, body, stage_all, fill, draft
        return PullRequestWorkflowResult(
            commit_message=message or "feat(cli): add contract checks",
            branch="feature/contracts",
            pull_request_url="https://github.com/example/repo/pull/1",
        )


class _ReviewerDouble:
    """Double for the review-service protocol."""

    def review(
        self,
        *,
        pr_number: int | None = None,
        mode: str = "general",
        refresh: bool = False,
    ) -> ReviewReport:
        del pr_number, refresh
        return ReviewReport(
            mode="security" if mode == "security" else "general",
            target="PR #1",
            summary="One finding",
            findings=(
                ReviewFinding(
                    code="SEC001",
                    severity="high",
                    file_path="src/henchman/api/server.py",
                    line_number=10,
                    message="Example issue",
                    suggestion="Fix it",
                    excerpt=None,
                    fixable=True,
                ),
            ),
        )


class _CommentManagerDouble:
    """Double for the PR comment-manager protocol."""

    def generate(self, *, pr_number: int) -> tuple[CommentDraft, ...]:
        return (
            CommentDraft(
                comment_id=pr_number,
                original_body="Please address this.",
                draft_reply="Fixed in the latest revision.",
                path="src/henchman/testing/contract.py",
            ),
        )

    def respond(self, *, pr_number: int, comment_id: int, body: str) -> CommentReplyResult:
        return CommentReplyResult(
            pr_number=pr_number,
            comment_id=comment_id,
            body=body,
            reply_url="https://github.com/example/repo/pull/1#discussion_r1",
        )


class _AutofixServiceDouble:
    """Double for the autofix-service protocol."""

    def autofix(
        self,
        *,
        pr_number: int | None = None,
        refresh: bool = False,
        apply: bool = False,
    ) -> AutofixReport:
        del pr_number, refresh
        return AutofixReport(
            applied_count=1 if apply else 0,
            skipped_count=0 if apply else 1,
            changes=(
                AutofixChange(
                    finding_code="SEC001",
                    file_path="src/henchman/api/server.py",
                    line_number=10,
                    applied=apply,
                    description="Sanitize one response",
                ),
            ),
        )


class _GitHubAppServiceDouble:
    """Double for the GitHub App service protocol."""

    def install(
        self,
        *,
        app_url: str,
        repo_slug: str | None = None,
        installation_id: int | None = None,
        webhook_secret_env: str = "HENCHMAN_GITHUB_WEBHOOK_SECRET",
        open_browser: bool = False,
    ) -> GitHubAppInstallRecord:
        del open_browser
        return GitHubAppInstallRecord(
            app_url=app_url,
            repo_slug=repo_slug,
            installation_id=installation_id,
            webhook_secret_env=webhook_secret_env,
            metadata_path=Path(".henchman/github/app_installation.json"),
        )


class _ToolCallDouble:
    """Double for the textual widget tool-call protocol."""

    def __init__(self) -> None:
        self.name = "read_file"
        self.arguments = {"path": "README.md"}


async def _agent_loop_runner_double(params: AgentLoopParams) -> AsyncIterator[AgentEvent]:
    """Double for the orchestrator loop-runner protocol."""
    yield AgentEvent(
        type=EventType.CONTENT,
        data=params.input_text,
        source_agent=params.target_role,
    )


def test_git_workflow_payload_contracts(contract_suite) -> None:
    """Git workflow service payloads should satisfy the CLI boundary contracts."""
    assistant = _accept_commit_assistant(_CommitAssistantDouble())
    branches = _accept_branch_manager(_BranchManagerDouble())
    workflow = _accept_workflow(_WorkflowDouble())

    assert_contract_matches(
        payload=assistant.suggest().to_dict(),
        schema_name="cli/commit_suggestion",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=branches.list()[0].to_dict(),
        schema_name="cli/branch_info",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=branches.create("feature/contracts").to_dict(),
        schema_name="cli/branch_operation",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=workflow.run().to_dict(),
        schema_name="cli/pull_request_workflow_result",
        contract_suite=contract_suite,
    )


def test_pull_request_payload_contracts(contract_suite) -> None:
    """PR review/comment/autofix services should satisfy the CLI boundary contracts."""
    reviewer = _accept_reviewer(_ReviewerDouble())
    comments = _accept_comment_manager(_CommentManagerDouble())
    autofix = _accept_autofix_service(_AutofixServiceDouble())
    github_app = _accept_github_app_service(_GitHubAppServiceDouble())

    assert_contract_matches(
        payload=reviewer.review().to_dict(),
        schema_name="cli/review_report",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=comments.generate(pr_number=7)[0].to_dict(),
        schema_name="cli/comment_draft",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=comments.respond(pr_number=7, comment_id=3, body="done").to_dict(),
        schema_name="cli/comment_reply_result",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=autofix.autofix(apply=True).to_dict(),
        schema_name="cli/autofix_report",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=github_app.install(app_url="https://github.com/apps/example").to_dict(),
        schema_name="cli/github_app_install_record",
        contract_suite=contract_suite,
    )


def test_textual_tool_call_protocol_shape() -> None:
    """Textual widgets should rely only on the documented tool-call shape."""
    tool_call = _accept_tool_call(_ToolCallDouble())

    assert tool_call.name == "read_file"
    assert tool_call.arguments == {"path": "README.md"}


@pytest.mark.anyio
async def test_agent_loop_runner_protocol_shape() -> None:
    """The orchestrator loop runner should stream agent events for one call."""
    runner = _accept_agent_loop_runner(_agent_loop_runner_double)
    params = AgentLoopParams(target_role="architect", input_text="hello")

    events = [event async for event in runner(params)]

    assert len(events) == 1
    assert events[0].type == EventType.CONTENT
    assert events[0].data == "hello"
    assert events[0].source_agent == "architect"


def test_agent_loop_runner_event_payload_matches_runtime_contract(contract_suite) -> None:
    """Loop-runner emitted events should satisfy the shared agent-event contract."""
    event = AgentEvent(
        type=EventType.CONTENT,
        data="hello",
        source_agent="architect",
    )

    assert_contract_matches(
        payload=serialize_contract_value(event),
        schema_name="runtime/agent_event",
        contract_suite=contract_suite,
    )


# ===========================================================================
# Git clients payload contracts (src/henchman/git/clients.py)
# ===========================================================================


class TestGitClientsContract:
    """Git client dataclass payloads must satisfy their CLI boundary contracts.

    Covers CommandResult and PullRequestComment from git/clients.py.
    """

    def test_command_result_matches_contract(self, contract_suite: object) -> None:
        """CommandResult shape must satisfy the command_result schema."""
        result = CommandResult(
            argv=("git", "status"),
            returncode=0,
            stdout="On branch main",
            stderr="",
        )
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=serialize_contract_value(result),
            schema_name="cli/command_result",
        )

    def test_command_result_with_error_matches_contract(self, contract_suite: object) -> None:
        """CommandResult with non-zero exit should still match."""
        result = CommandResult(
            argv=("git", "log", "--invalid"),
            returncode=128,
            stdout="",
            stderr="fatal: unrecognized argument: --invalid",
        )
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=serialize_contract_value(result),
            schema_name="cli/command_result",
        )

    def test_pull_request_comment_matches_contract(self, contract_suite: object) -> None:
        """PullRequestComment shape must satisfy the pull_request_comment schema."""
        comment = PullRequestComment(
            comment_id=42,
            body="Please use a helper function here.",
            path="src/main.py",
            author="reviewer-bot",
            url="https://github.com/example/repo/pull/1#discussion_r42",
        )
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=serialize_contract_value(comment),
            schema_name="cli/pull_request_comment",
        )

    def test_pull_request_comment_minimal_matches_contract(self, contract_suite: object) -> None:
        """PullRequestComment with null fields should still match."""
        comment = PullRequestComment(
            comment_id=1,
            body="LGTM",
            path=None,
            author=None,
            url=None,
        )
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=serialize_contract_value(comment),
            schema_name="cli/pull_request_comment",
        )
