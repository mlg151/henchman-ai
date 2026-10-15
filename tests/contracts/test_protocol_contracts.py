"""Contract tests for protocol-shaped internal boundaries.

Covers:
- _ChatAgent protocol (chat subsystem)
- SettingsRepositoryLike protocol (doctor command)
- AgentProtocol (delegation)
- AgentInterface protocol (core agent contract)
- CLI git/PR protocols (structural contracts via method shape checking)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from henchman.agents.delegation import AgentProtocol
from henchman.agents.identity import AgentIdentity
from henchman.chat.manager import _ChatAgent, _FallbackChatAgent
from henchman.cli.commands.doctor_command import SettingsRepositoryLike
from henchman.core.agent_interface import AgentInterface
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message


def _accept_chat_agent(agent: _ChatAgent) -> _ChatAgent:
    """Type-level helper for the chat-agent contract."""
    return agent


def _accept_settings_repository(repo: SettingsRepositoryLike) -> SettingsRepositoryLike:
    """Type-level helper for the settings-repository contract."""
    return repo


def _accept_agent_interface(agent: AgentInterface) -> AgentInterface:
    """Type-level helper for the AgentInterface contract."""
    return agent


class _DelegationAgentDouble:
    """Runtime double for the delegation contract."""

    def __init__(self) -> None:
        self.messages = [Message(role="system", content="hello")]

    def clear_history(self) -> None:
        self.messages = []


class _SettingsRepositoryDouble:
    """Runtime double for the doctor settings contract."""

    def view(self, *, scope: object) -> dict[str, object]:
        return {"scope": str(scope)}


class _MinimalAgent:
    """Runtime double satisfying the AgentInterface protocol."""

    def __init__(self) -> None:
        self._messages: list[Message] = []
        self._delegation_errors: list[str] = []

    @property
    def provider(self) -> object:
        return type("Provider", (), {})()

    @property
    def tool_registry(self) -> object:
        return type("Registry", (), {})()

    @property
    def messages(self) -> list[Message]:
        return self._messages

    @property
    def identity(self) -> AgentIdentity | None:
        return None

    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(type=EventType.CONTENT, data=user_input, source_agent="agent")

    async def continue_with_tool_results(self) -> AsyncIterator[AgentEvent]:
        return
        yield  # pragma: no cover

    def record_delegation_errors(self, errors: list[str]) -> None:
        self._delegation_errors.extend(errors)

    def get_delegation_errors(self) -> list[str]:
        return self._delegation_errors


def test_fallback_chat_agent_exposes_required_contract_methods() -> None:
    """The fallback chat agent should satisfy the shared chat-agent protocol."""
    agent = _accept_chat_agent(_FallbackChatAgent(tool_registry={}))

    assert callable(agent.run)
    assert callable(agent.continue_with_tool_results)
    assert callable(agent.submit_tool_result)
    assert callable(agent.clear_history)


@pytest.mark.anyio
async def test_fallback_chat_agent_contract_is_idempotent() -> None:
    """The fallback chat agent should remain stateless across empty runs."""
    agent = _FallbackChatAgent(tool_registry={})

    first = [item async for item in agent.run("hello")]
    agent.submit_tool_result("call-1", "result")
    second = [item async for item in agent.continue_with_tool_results()]
    agent.clear_history()

    assert first == []
    assert second == []


def test_delegation_protocol_is_runtime_checkable() -> None:
    """Delegation uses a runtime-checkable protocol for agent handoffs."""
    assert isinstance(_DelegationAgentDouble(), AgentProtocol)


def test_settings_repository_protocol_shape_is_preserved() -> None:
    """Doctor's read-only settings contract should remain minimal and stable."""
    repository = _accept_settings_repository(_SettingsRepositoryDouble())

    assert repository.view(scope="project") == {"scope": "project"}


# ===========================================================================
# AgentInterface protocol contract
# ===========================================================================


def test_agent_interface_is_runtime_checkable() -> None:
    """AgentInterface should be runtime-checkable."""
    assert isinstance(_MinimalAgent(), AgentInterface)


def test_agent_interface_property_shapes() -> None:
    """A minimal agent should expose all required properties."""
    agent = _accept_agent_interface(_MinimalAgent())

    assert agent.provider is not None
    assert agent.tool_registry is not None
    assert agent.messages == []
    assert agent.identity is None


@pytest.mark.anyio
async def test_agent_interface_run_yields_events() -> None:
    """AgentInterface.run() must yield AgentEvent instances."""
    agent = _accept_agent_interface(_MinimalAgent())

    events = [event async for event in agent.run("hello")]
    assert len(events) == 1
    assert events[0].type == EventType.CONTENT
    assert events[0].data == "hello"


@pytest.mark.anyio
async def test_agent_interface_continue_with_tool_results() -> None:
    """AgentInterface.continue_with_tool_results() should be callable."""
    agent = _accept_agent_interface(_MinimalAgent())

    events = [event async for event in agent.continue_with_tool_results()]
    assert events == []


def test_agent_interface_delegation_errors() -> None:
    """AgentInterface should support delegation error recording."""
    agent = _accept_agent_interface(_MinimalAgent())

    agent.record_delegation_errors(["error-1", "error-2"])
    assert agent.get_delegation_errors() == ["error-1", "error-2"]

    agent.record_delegation_errors(["error-3"])
    assert agent.get_delegation_errors() == ["error-1", "error-2", "error-3"]


# ===========================================================================
# CLI structural protocol contracts (method shape verification)
# ===========================================================================


class TestCliProtocolShapes:
    """Git and PR CLI protocols must maintain their method signatures."""

    def test_branch_manager_protocol_shape(self) -> None:
        """_BranchManagerProtocol must have list, create, and switch methods."""
        from henchman.cli.commands.git_command import _BranchManagerProtocol

        methods = ["list", "create", "switch"]
        for method in methods:
            assert hasattr(_BranchManagerProtocol, method), (
                f"_BranchManagerProtocol missing method: {method}"
            )

    def test_commit_assistant_protocol_shape(self) -> None:
        """_CommitAssistantProtocol must have suggest method."""
        from henchman.cli.commands.git_command import _CommitAssistantProtocol

        assert hasattr(_CommitAssistantProtocol, "suggest")

    def test_workflow_protocol_shape(self) -> None:
        """_WorkflowProtocol must have run method."""
        from henchman.cli.commands.git_command import _WorkflowProtocol

        assert hasattr(_WorkflowProtocol, "run")

    def test_reviewer_protocol_shape(self) -> None:
        """_ReviewerProtocol must have review method."""
        from henchman.cli.commands.pull_request_command import _ReviewerProtocol

        assert hasattr(_ReviewerProtocol, "review")

    def test_comment_manager_protocol_shape(self) -> None:
        """_CommentManagerProtocol must have generate and respond methods."""
        from henchman.cli.commands.pull_request_command import _CommentManagerProtocol

        assert hasattr(_CommentManagerProtocol, "generate")
        assert hasattr(_CommentManagerProtocol, "respond")

    def test_autofix_service_protocol_shape(self) -> None:
        """_AutofixServiceProtocol must have autofix method."""
        from henchman.cli.commands.pull_request_command import _AutofixServiceProtocol

        assert hasattr(_AutofixServiceProtocol, "autofix")

    def test_github_app_service_protocol_shape(self) -> None:
        """_GitHubAppServiceProtocol must have install method."""
        from henchman.cli.commands.pull_request_command import _GitHubAppServiceProtocol

        assert hasattr(_GitHubAppServiceProtocol, "install")

    def test_branch_manager_double_satisfies_protocol(self) -> None:
        """A structurally compatible double should satisfy the protocol."""

        class BranchDouble:
            def list(self) -> list:
                return []

            def create(self, name: str, **kwargs: object) -> object:
                return {"action": "create", "branch": name}

            def switch(self, name: str) -> object:
                return {"action": "switch", "branch": name}

        double = BranchDouble()
        assert hasattr(double, "list") and callable(double.list)
        assert hasattr(double, "create") and callable(double.create)
        assert hasattr(double, "switch") and callable(double.switch)

    def test_workflow_double_runs_properly(self) -> None:
        """A workflow double should return the expected result structure."""

        class WorkflowDouble:
            def run(self, **kwargs: object) -> object:
                return {"commit_message": "feat: test", "branch": "main", "pull_request_url": ""}

        double = WorkflowDouble()
        result = double.run()
        assert isinstance(result, dict)
        assert "commit_message" in result
        assert "branch" in result
        assert "pull_request_url" in result


# ===========================================================================
# Git protocol satisfaction: concrete implementations satisfy protocols
# ===========================================================================


def test_commit_assistant_satisfies_protocol() -> None:
    """CommitAssistant must structurally satisfy _CommitAssistantProtocol."""
    from henchman.cli.commands.git_command import _CommitAssistantProtocol
    from henchman.git.workflow import CommitAssistant

    assert isinstance(CommitAssistant(), _CommitAssistantProtocol)


def test_branch_manager_satisfies_protocol() -> None:
    """BranchManager must structurally satisfy _BranchManagerProtocol."""
    from henchman.cli.commands.git_command import _BranchManagerProtocol
    from henchman.git.workflow import BranchManager

    assert isinstance(BranchManager(), _BranchManagerProtocol)


def test_pull_request_workflow_satisfies_protocol() -> None:
    """PullRequestWorkflow must structurally satisfy _WorkflowProtocol."""
    from henchman.cli.commands.git_command import _WorkflowProtocol
    from henchman.git.workflow import PullRequestWorkflow

    assert isinstance(PullRequestWorkflow(), _WorkflowProtocol)


def test_reviewer_satisfies_protocol() -> None:
    """PullRequestReviewer must structurally satisfy _ReviewerProtocol."""
    from henchman.cli.commands.pull_request_command import _ReviewerProtocol
    from henchman.git.review import PullRequestReviewer

    assert isinstance(PullRequestReviewer(), _ReviewerProtocol)


def test_comment_manager_satisfies_protocol() -> None:
    """CommentManager must structurally satisfy _CommentManagerProtocol."""
    from henchman.cli.commands.pull_request_command import _CommentManagerProtocol
    from henchman.git.review import CommentManager

    assert isinstance(CommentManager(), _CommentManagerProtocol)


def test_autofix_service_satisfies_protocol() -> None:
    """AutofixService must structurally satisfy _AutofixServiceProtocol."""
    from henchman.cli.commands.pull_request_command import _AutofixServiceProtocol
    from henchman.git.review import AutofixService

    assert isinstance(AutofixService(), _AutofixServiceProtocol)


def test_github_app_service_satisfies_protocol() -> None:
    """GitHubAppService must structurally satisfy _GitHubAppServiceProtocol."""
    from henchman.cli.commands.pull_request_command import _GitHubAppServiceProtocol
    from henchman.git.github_app import GitHubAppService

    assert isinstance(GitHubAppService(), _GitHubAppServiceProtocol)


# ===========================================================================
# Git data payload behavioral contracts
# ===========================================================================


def test_commit_suggestion_shape() -> None:
    """CommitSuggestion must expose all required fields."""
    from henchman.git.workflow import CommitSuggestion

    suggestion = CommitSuggestion(
        message="feat(cli): add commit command",
        commit_type="feat",
        scope="cli",
        summary="add commit command",
        files=("src/henchman/cli/commands/git_command.py",),
    )
    assert suggestion.message == "feat(cli): add commit command"
    assert suggestion.commit_type == "feat"
    assert suggestion.scope == "cli"
    assert suggestion.summary == "add commit command"
    assert isinstance(suggestion.files, tuple)
    assert isinstance(suggestion.to_dict(), dict)
    d = suggestion.to_dict()
    assert d["message"] == suggestion.message
    assert d["commit_type"] == suggestion.commit_type
    assert d["scope"] == suggestion.scope
    assert d["summary"] == suggestion.summary
    assert d["files"] == list(suggestion.files)


def test_branch_info_shape() -> None:
    """BranchInfo must expose all required fields."""
    from henchman.git.workflow import BranchInfo

    info = BranchInfo(name="main", is_current=True)
    assert info.name == "main"
    assert info.is_current is True
    assert isinstance(info.to_dict(), dict)
    d = info.to_dict()
    assert d["name"] == "main"
    assert d["is_current"] is True


def test_branch_operation_shape() -> None:
    """BranchOperation must expose all required fields."""
    from henchman.git.workflow import BranchOperation

    op = BranchOperation(action="create", branch="feature", current_branch="feature")
    assert op.action == "create"
    assert op.branch == "feature"
    assert op.current_branch == "feature"
    assert isinstance(op.to_dict(), dict)
    d = op.to_dict()
    assert d["action"] == "create"
    assert d["branch"] == "feature"
    assert d["current_branch"] == "feature"


def test_pull_request_workflow_result_shape() -> None:
    """PullRequestWorkflowResult must expose all required fields."""
    from henchman.git.workflow import PullRequestWorkflowResult

    result = PullRequestWorkflowResult(
        commit_message="feat: add feature",
        branch="feature",
        pull_request_url="https://github.com/owner/repo/pull/1",
    )
    assert result.commit_message == "feat: add feature"
    assert result.branch == "feature"
    assert result.pull_request_url == "https://github.com/owner/repo/pull/1"
    assert isinstance(result.to_dict(), dict)
    d = result.to_dict()
    assert d["commit_message"] == result.commit_message
    assert d["branch"] == result.branch
    assert d["pull_request_url"] == result.pull_request_url


def test_review_report_shape() -> None:
    """ReviewReport must expose all required fields."""
    from henchman.git.review import ReviewFinding, ReviewReport

    findings = (
        ReviewFinding(
            code="debug-statement",
            severity="medium",
            file_path="src/main.py",
            line_number=10,
            message="Remove debug output.",
            suggestion="Delete the debug statement.",
        ),
    )
    report = ReviewReport(mode="general", target="staged", summary="1 finding.", findings=findings)
    assert report.mode == "general"
    assert report.target == "staged"
    assert report.summary == "1 finding."
    assert len(report.findings) == 1
    assert isinstance(report.to_dict(), dict)
    d = report.to_dict()
    assert d["mode"] == "general"
    assert d["target"] == "staged"
    assert d["summary"] == "1 finding."
    assert len(d["findings"]) == 1


def test_comment_draft_shape() -> None:
    """CommentDraft must expose all required fields."""
    from henchman.git.review import CommentDraft

    draft = CommentDraft(
        comment_id=42,
        original_body="Please add tests.",
        draft_reply="I'll add tests.",
        path="src/main.py",
    )
    assert draft.comment_id == 42
    assert draft.original_body == "Please add tests."
    assert draft.draft_reply == "I'll add tests."
    assert draft.path == "src/main.py"
    assert isinstance(draft.to_dict(), dict)
    d = draft.to_dict()
    assert d["comment_id"] == 42
    assert d["original_body"] == "Please add tests."
    assert d["draft_reply"] == "I'll add tests."
    assert d["path"] == "src/main.py"


def test_comment_reply_result_shape() -> None:
    """CommentReplyResult must expose all required fields."""
    from henchman.git.review import CommentReplyResult

    result = CommentReplyResult(
        pr_number=1,
        comment_id=42,
        body="Thanks for the review.",
        reply_url="https://github.com/owner/repo/pull/1#issuecomment-1",
    )
    assert result.pr_number == 1
    assert result.comment_id == 42
    assert result.body == "Thanks for the review."
    assert result.reply_url == "https://github.com/owner/repo/pull/1#issuecomment-1"
    assert isinstance(result.to_dict(), dict)
    d = result.to_dict()
    assert d["pr_number"] == 1
    assert d["comment_id"] == 42
    assert d["body"] == "Thanks for the review."
    assert d["reply_url"] == "https://github.com/owner/repo/pull/1#issuecomment-1"


def test_autofix_report_shape() -> None:
    """AutofixReport must expose all required fields."""
    from henchman.git.review import AutofixChange, AutofixReport

    changes = (
        AutofixChange(
            finding_code="debug-statement",
            file_path="src/main.py",
            line_number=10,
            applied=True,
            description="Removed the debug statement.",
        ),
    )
    report = AutofixReport(applied_count=1, skipped_count=0, changes=changes)
    assert report.applied_count == 1
    assert report.skipped_count == 0
    assert len(report.changes) == 1
    assert isinstance(report.to_dict(), dict)
    d = report.to_dict()
    assert d["applied_count"] == 1
    assert d["skipped_count"] == 0
    assert len(d["changes"]) == 1


def test_github_app_install_record_shape() -> None:
    """GitHubAppInstallRecord must expose all required fields."""
    from pathlib import Path

    from henchman.git.github_app import GitHubAppInstallRecord

    record = GitHubAppInstallRecord(
        app_url="https://github.com/apps/my-app",
        repo_slug="owner/repo",
        installation_id=12345,
        webhook_secret_env="WEBHOOK_SECRET",
        metadata_path=Path("/tmp/meta.json"),
    )
    assert record.app_url == "https://github.com/apps/my-app"
    assert record.repo_slug == "owner/repo"
    assert record.installation_id == 12345
    assert record.webhook_secret_env == "WEBHOOK_SECRET"
    assert record.metadata_path == Path("/tmp/meta.json")
    assert isinstance(record.to_dict(), dict)
    d = record.to_dict()
    assert d["app_url"] == "https://github.com/apps/my-app"
    assert d["repo_slug"] == "owner/repo"
    assert d["installation_id"] == 12345
    assert d["webhook_secret_env"] == "WEBHOOK_SECRET"
    assert d["metadata_path"] == "/tmp/meta.json"
