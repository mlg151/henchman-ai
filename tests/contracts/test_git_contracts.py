"""Contract tests for git client subsystem boundaries."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict
from pathlib import Path

import pytest

from henchman.git.clients import (
    CommandExecutionError,
    CommandResult,
    GitClient,
    GitHubCliClient,
    PullRequestComment,
    run_command,
)
from henchman.testing.contract import ContractSuite

# ===========================================================================
# CommandResult dataclass contract
# ===========================================================================


class TestCommandResultContract:
    """CommandResult must conform to the expected data shape."""

    def test_required_fields(self) -> None:
        """CommandResult must have all required fields."""
        result = CommandResult(
            argv=("git", "status"),
            returncode=0,
            stdout="On branch main\n",
            stderr="",
        )
        assert result.argv == ("git", "status")
        assert result.returncode == 0
        assert result.stdout == "On branch main\n"
        assert result.stderr == ""

    def test_is_frozen(self) -> None:
        """CommandResult must be immutable (frozen dataclass)."""
        result = CommandResult(
            argv=("git", "status"),
            returncode=0,
            stdout="",
            stderr="",
        )
        with pytest.raises(FrozenInstanceError):
            result.stdout = "modified"  # type: ignore[misc]

    def test_matches_contract(self, contract_suite: ContractSuite) -> None:
        """CommandResult payload must match the contract schema."""
        result = CommandResult(
            argv=("git", "diff", "--cached"),
            returncode=0,
            stdout="diff --git a/file.txt b/file.txt\n",
            stderr="",
        )
        schema = {
            "argv": tuple,
            "returncode": int,
            "stdout": str,
            "stderr": str,
        }
        errors = contract_suite.validate(asdict(result), schema)
        assert errors == [], f"Contract validation failed: {errors}"


# ===========================================================================
# CommandExecutionError contract
# ===========================================================================


class TestCommandExecutionErrorContract:
    """CommandExecutionError must wrap CommandResult correctly."""

    def test_error_wraps_result(self) -> None:
        """CommandExecutionError must store the CommandResult."""
        result = CommandResult(
            argv=("git", "push"),
            returncode=1,
            stdout="",
            stderr="error: failed to push",
        )
        error = CommandExecutionError(result)
        assert error.result is result
        assert "error: failed to push" in str(error)

    def test_error_message_from_stderr(self) -> None:
        """Error message should come from stderr when available."""
        result = CommandResult(
            argv=("git", "commit"),
            returncode=1,
            stdout="",
            stderr="nothing to commit",
        )
        error = CommandExecutionError(result)
        assert "nothing to commit" in str(error)

    def test_error_message_fallback_to_stdout(self) -> None:
        """Error message should fall back to stdout when stderr is empty."""
        result = CommandResult(
            argv=("git", "diff"),
            returncode=1,
            stdout="diff output here",
            stderr="",
        )
        error = CommandExecutionError(result)
        assert "diff output here" in str(error)

    def test_error_message_fallback_default(self) -> None:
        """Error message should use default when both streams are empty."""
        result = CommandResult(
            argv=("git", "unknown"),
            returncode=1,
            stdout="",
            stderr="",
        )
        error = CommandExecutionError(result)
        assert "Command execution failed" in str(error)


# ===========================================================================
# PullRequestComment dataclass contract
# ===========================================================================


class TestPullRequestCommentContract:
    """PullRequestComment must conform to the expected data shape."""

    def test_required_fields(self) -> None:
        """PullRequestComment must have all required fields."""
        comment = PullRequestComment(
            comment_id=12345,
            body="LGTM",
            path="src/main.py",
            author="alice",
            url="https://github.com/owner/repo/pull/1#discussion_r12345",
        )
        assert comment.comment_id == 12345
        assert comment.body == "LGTM"
        assert comment.path == "src/main.py"
        assert comment.author == "alice"
        assert comment.url == "https://github.com/owner/repo/pull/1#discussion_r12345"

    def test_optional_fields_accept_none(self) -> None:
        """Optional fields should accept None values."""
        comment = PullRequestComment(
            comment_id=12345,
            body="LGTM",
            path=None,
            author=None,
            url=None,
        )
        assert comment.path is None
        assert comment.author is None
        assert comment.url is None

    def test_is_frozen(self) -> None:
        """PullRequestComment must be immutable (frozen dataclass)."""
        comment = PullRequestComment(
            comment_id=12345,
            body="LGTM",
            path="src/main.py",
            author="alice",
            url="https://example.com",
        )
        with pytest.raises(FrozenInstanceError):
            comment.body = "modified"  # type: ignore[misc]

    def test_matches_contract(self, contract_suite: ContractSuite) -> None:
        """PullRequestComment payload must match the contract schema."""
        comment = PullRequestComment(
            comment_id=42,
            body="Needs tests",
            path="src/module.py",
            author="bob",
            url="https://example.com/comment",
        )
        schema = {
            "comment_id": int,
            "body": str,
            "path": str,
            "author": str,
            "url": str,
        }
        errors = contract_suite.validate(asdict(comment), schema)
        assert errors == [], f"Contract validation failed: {errors}"


# ===========================================================================
# run_command contract
# ===========================================================================


class TestRunCommandContract:
    """run_command must return a valid CommandResult."""

    def test_returns_command_result(self, tmp_path: Path) -> None:
        """run_command must return a CommandResult with correct structure."""
        result = run_command(["echo", "hello"], cwd=tmp_path)
        assert isinstance(result, CommandResult)
        assert result.returncode == 0
        assert "hello" in result.stdout
        assert result.stderr == ""

    def test_captures_nonzero_exit(self, tmp_path: Path) -> None:
        """run_command must capture non-zero exit codes without raising."""
        result = run_command(["sh", "-c", "exit 1"], cwd=tmp_path)
        assert result.returncode == 1

    def test_captures_stderr(self, tmp_path: Path) -> None:
        """run_command must capture stderr output."""
        result = run_command(["sh", "-c", "echo error >&2"], cwd=tmp_path)
        assert "error" in result.stderr


# ===========================================================================
# GitClient contract
# ===========================================================================


class TestGitClientContract:
    """GitClient must satisfy the git operations interface contract."""

    def _make_client(
        self,
        project_root: Path | None = None,
        runner: object = None,
    ) -> GitClient:
        return GitClient(project_root=project_root, runner=runner)

    def test_changed_files_staged(self, tmp_path: Path) -> None:
        """changed_files must return a tuple of file paths."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="file1.py\nfile2.py\n",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        files = client.changed_files(staged_only=True)
        assert isinstance(files, tuple)
        assert "file1.py" in files
        assert "file2.py" in files

    def test_changed_files_unstaged(self, tmp_path: Path) -> None:
        """changed_files with staged_only=False must parse status output."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout=" M file1.py\n?? file2.py\n",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        files = client.changed_files(staged_only=False)
        assert isinstance(files, tuple)
        assert "file1.py" in files
        assert "file2.py" in files

    def test_changed_files_empty(self, tmp_path: Path) -> None:
        """changed_files must return empty tuple when no changes."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        files = client.changed_files()
        assert files == ()

    def test_diff_returns_stdout(self, tmp_path: Path) -> None:
        """diff must return the captured stdout as a string."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="diff --git a/file b/file\n",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        output = client.diff(staged=True)
        assert isinstance(output, str)
        assert "diff --git" in output

    def test_current_branch(self, tmp_path: Path) -> None:
        """current_branch must return the branch name string."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="feature-branch\n",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        branch = client.current_branch()
        assert branch == "feature-branch"

    def test_list_branches(self, tmp_path: Path) -> None:
        """list_branches must return tuples of (name, is_current)."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="*|main\n |feature\n",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        branches = client.list_branches()
        assert isinstance(branches, tuple)
        assert ("main", True) in branches
        assert ("feature", False) in branches

    def test_create_branch_returns_name(self, tmp_path: Path) -> None:
        """create_branch must return the branch name."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            if "branch" in argv and "--show-current" not in argv:
                return CommandResult(
                    argv=tuple(argv),
                    returncode=0,
                    stdout="",
                    stderr="",
                )
            # current_branch() call
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="new-branch\n",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        name = client.create_branch("new-branch")
        assert name == "new-branch"

    def test_switch_branch_returns_name(self, tmp_path: Path) -> None:
        """switch_branch must return the branch name."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        name = client.switch_branch("existing-branch")
        assert name == "existing-branch"

    def test_commit_no_error(self, tmp_path: Path) -> None:
        """commit must not raise on success."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        client.commit("Test commit")  # Should not raise

    def test_push_current_branch(self, tmp_path: Path) -> None:
        """push_current_branch must return the branch name."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            if "branch" in str(argv):
                return CommandResult(argv=tuple(argv), returncode=0, stdout="main\n", stderr="")
            return CommandResult(argv=tuple(argv), returncode=0, stdout="", stderr="")

        client = self._make_client(tmp_path, runner=fake_runner)
        branch = client.push_current_branch()
        assert isinstance(branch, str)

    def test_nonzero_raises_command_execution_error(self, tmp_path: Path) -> None:
        """GitClient methods must raise CommandExecutionError on non-zero exit."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=1,
                stdout="",
                stderr="fatal: not a git repository",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        with pytest.raises(CommandExecutionError, match="fatal: not a git repository"):
            client.current_branch()


# ===========================================================================
# GitHubCliClient contract
# ===========================================================================


class TestGitHubCliClientContract:
    """GitHubCliClient must satisfy the GitHub CLI interface contract."""

    def _make_client(
        self,
        project_root: Path | None = None,
        runner: object = None,
    ) -> GitHubCliClient:
        return GitHubCliClient(project_root=project_root, runner=runner)

    def test_repo_name_with_owner(self, tmp_path: Path) -> None:
        """repo_name_with_owner must return owner/name string."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="owner/repo-name\n",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        name = client.repo_name_with_owner()
        assert name == "owner/repo-name"

    def test_create_pull_request_returns_url(self, tmp_path: Path) -> None:
        """create_pull_request must return the PR URL."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="https://github.com/owner/repo/pull/42\n",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        url = client.create_pull_request(title="Fix bug", body="Description")
        assert url == "https://github.com/owner/repo/pull/42"

    def test_pull_request_diff(self, tmp_path: Path) -> None:
        """pull_request_diff must return diff output."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="diff --git a/file b/file\n@@ -1 +1 @@\n",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        diff = client.pull_request_diff(42)
        assert "diff --git" in diff

    def test_fetch_review_comments(self, tmp_path: Path) -> None:
        """fetch_review_comments must return PullRequestComment tuples."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout='[{"id": 1, "body": "nit: style", "path": "src/a.py", "user": {"login": "bob"}, "html_url": "https://example.com/1"}]',
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        comments = client.fetch_review_comments(42)
        assert isinstance(comments, tuple)
        assert len(comments) == 1
        assert comments[0].comment_id == 1
        assert comments[0].body == "nit: style"
        assert comments[0].author == "bob"

    def test_fetch_review_comments_empty(self, tmp_path: Path) -> None:
        """fetch_review_comments must return empty tuple for no comments."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="[]",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        comments = client.fetch_review_comments(42)
        assert comments == ()

    def test_fetch_review_comments_invalid_json_raises(self, tmp_path: Path) -> None:
        """fetch_review_comments must raise ValueError on invalid JSON."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="not json",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        with pytest.raises(ValueError, match="invalid JSON"):
            client.fetch_review_comments(42)

    def test_reply_to_review_comment_returns_url(self, tmp_path: Path) -> None:
        """reply_to_review_comment must return the reply URL."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout='{"html_url": "https://github.com/owner/repo/pull/42#discussion_r999"}',
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        url = client.reply_to_review_comment(
            pr_number=42,
            comment_id=123,
            body="Fixed in latest commit",
        )
        assert url == "https://github.com/owner/repo/pull/42#discussion_r999"

    def test_reply_to_review_comment_invalid_json_raises(self, tmp_path: Path) -> None:
        """reply_to_review_comment must raise ValueError on invalid JSON."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=0,
                stdout="not json",
                stderr="",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        with pytest.raises(ValueError, match="invalid JSON"):
            client.reply_to_review_comment(pr_number=42, comment_id=1, body="thanks")

    def test_nonzero_raises_command_execution_error(self, tmp_path: Path) -> None:
        """GitHubCliClient methods must raise on non-zero exit."""

        def fake_runner(argv: list[str], _cwd: Path | None) -> CommandResult:
            return CommandResult(
                argv=tuple(argv),
                returncode=1,
                stdout="",
                stderr="gh: not authenticated",
            )

        client = self._make_client(tmp_path, runner=fake_runner)
        with pytest.raises(CommandExecutionError, match="gh: not authenticated"):
            client.repo_name_with_owner()
