"""Low-level git and GitHub CLI clients."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

Runner = Callable[[list[str], Path | None], "CommandResult"]


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured result from executing one argv-only command."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CommandExecutionError(RuntimeError):
    """Raised when a git or GitHub CLI command returns a non-zero exit status."""

    def __init__(self, result: CommandResult) -> None:
        message = result.stderr.strip() or result.stdout.strip() or "Command execution failed."
        super().__init__(message)
        self.result = result


@dataclass(frozen=True, slots=True)
class PullRequestComment:
    """A GitHub pull-request review comment."""

    comment_id: int
    body: str
    path: str | None
    author: str | None
    url: str | None


def run_command(argv: list[str], cwd: Path | None = None) -> CommandResult:
    """Execute one local command using argv-only semantics.

    Args:
        argv: Argument vector to execute.
        cwd: Optional working directory for the command.

    Returns:
        The captured command result.
    """

    completed = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(
        argv=tuple(argv),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


class GitClient:
    """Thin wrapper around local git operations used by Tier 4 commands."""

    def __init__(self, project_root: Path | None = None, *, runner: Runner | None = None) -> None:
        """Initialize the client.

        Args:
            project_root: Optional repository root. Defaults to the current directory.
            runner: Optional test double for command execution.
        """

        self._project_root = (project_root or Path.cwd()).resolve()
        self._runner = runner or run_command

    def changed_files(self, *, staged_only: bool = True) -> tuple[str, ...]:
        """Return changed file paths for commit-message generation."""

        if staged_only:
            result = self._run(["git", "-C", str(self._project_root), "diff", "--cached", "--name-only"])
            lines = result.stdout.splitlines()
        else:
            result = self._run(["git", "-C", str(self._project_root), "status", "--short"])
            lines = [line[3:] for line in result.stdout.splitlines() if len(line) >= 4]
        return tuple(path.strip() for path in lines if path.strip())

    def diff(self, *, staged: bool = False) -> str:
        """Return a unified diff for staged or working-tree changes."""

        argv = ["git", "-C", str(self._project_root), "diff", "--no-ext-diff", "--unified=3"]
        if staged:
            argv.insert(4, "--cached")
        return self._run(argv).stdout

    def current_branch(self) -> str:
        """Return the currently checked out branch name."""

        result = self._run(["git", "-C", str(self._project_root), "branch", "--show-current"])
        return result.stdout.strip()

    def list_branches(self) -> tuple[tuple[str, bool], ...]:
        """Return available branches and whether each one is current."""

        result = self._run(
            [
                "git",
                "-C",
                str(self._project_root),
                "branch",
                "--format=%(HEAD)|%(refname:short)",
            ],
        )
        branches: list[tuple[str, bool]] = []
        for line in result.stdout.splitlines():
            marker, _, name = line.partition("|")
            branch_name = name.strip()
            if branch_name:
                branches.append((branch_name, marker.strip() == "*"))
        return tuple(branches)

    def create_branch(
        self,
        name: str,
        *,
        switch: bool = False,
        start_point: str | None = None,
    ) -> str:
        """Create a branch and optionally switch to it."""

        if switch:
            argv = ["git", "-C", str(self._project_root), "switch", "-c", name]
        else:
            argv = ["git", "-C", str(self._project_root), "branch", name]
        if start_point:
            argv.append(start_point)
        self._run(argv)
        return name if switch else self.current_branch()

    def switch_branch(self, name: str) -> str:
        """Switch to an existing branch."""

        self._run(["git", "-C", str(self._project_root), "switch", name])
        return name

    def commit(self, message: str, *, stage_all: bool = False) -> None:
        """Create one commit with the provided message."""

        if stage_all:
            self._run(["git", "-C", str(self._project_root), "add", "-A"])
        self._run(["git", "-C", str(self._project_root), "commit", "-m", message])

    def push_current_branch(self) -> str:
        """Push the current branch to origin with upstream tracking."""

        branch = self.current_branch()
        self._run(
            [
                "git",
                "-C",
                str(self._project_root),
                "push",
                "--set-upstream",
                "origin",
                "HEAD",
            ],
        )
        return branch

    def _run(self, argv: list[str]) -> CommandResult:
        """Execute one git command and raise on failure."""

        result = self._runner(argv, self._project_root)
        if result.returncode != 0:
            raise CommandExecutionError(result)
        return result


class GitHubCliClient:
    """Thin wrapper around the `gh` CLI for PR interactions."""

    def __init__(self, project_root: Path | None = None, *, runner: Runner | None = None) -> None:
        """Initialize the client.

        Args:
            project_root: Optional repository root. Defaults to the current directory.
            runner: Optional test double for command execution.
        """

        self._project_root = (project_root or Path.cwd()).resolve()
        self._runner = runner or run_command

    def repo_name_with_owner(self) -> str:
        """Return the currently selected repository as `owner/name`."""

        result = self._run(
            [
                "gh",
                "repo",
                "view",
                "--json",
                "nameWithOwner",
                "--jq",
                ".nameWithOwner",
            ],
        )
        return result.stdout.strip()

    def create_pull_request(
        self,
        *,
        title: str | None,
        body: str | None,
        repo_slug: str | None = None,
        fill: bool = False,
        draft: bool = False,
    ) -> str:
        """Create one pull request and return its URL."""

        argv = ["gh", "pr", "create"]
        if repo_slug:
            argv.extend(["--repo", repo_slug])
        if title is not None:
            argv.extend(["--title", title])
        if body is not None:
            argv.extend(["--body", body])
        if fill:
            argv.append("--fill")
        if draft:
            argv.append("--draft")
        result = self._run(argv)
        return result.stdout.strip()

    def pull_request_diff(self, pr_number: int, *, repo_slug: str | None = None) -> str:
        """Return the unified diff for one pull request."""

        argv = ["gh", "pr", "diff", str(pr_number)]
        if repo_slug:
            argv.extend(["--repo", repo_slug])
        return self._run(argv).stdout

    def fetch_review_comments(
        self,
        pr_number: int,
        *,
        repo_slug: str | None = None,
    ) -> tuple[PullRequestComment, ...]:
        """Return review comments for one pull request."""

        resolved_repo = repo_slug or self.repo_name_with_owner()
        result = self._run(["gh", "api", f"repos/{resolved_repo}/pulls/{pr_number}/comments"])
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("GitHub CLI returned invalid JSON for review comments.") from exc
        if not isinstance(payload, list):
            raise ValueError("GitHub CLI returned an unexpected review comments payload.")
        comments: list[PullRequestComment] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            comment_id = item.get("id")
            body = item.get("body")
            if not isinstance(comment_id, int) or not isinstance(body, str):
                continue
            author = None
            user = item.get("user")
            if isinstance(user, dict):
                login = user.get("login")
                author = login if isinstance(login, str) else None
            path = item.get("path") if isinstance(item.get("path"), str) else None
            url = item.get("html_url") if isinstance(item.get("html_url"), str) else None
            comments.append(
                PullRequestComment(
                    comment_id=comment_id,
                    body=body,
                    path=path,
                    author=author,
                    url=url,
                ),
            )
        return tuple(comments)

    def reply_to_review_comment(
        self,
        *,
        pr_number: int,
        comment_id: int,
        body: str,
        repo_slug: str | None = None,
    ) -> str:
        """Reply to one pull-request review comment and return the reply URL."""

        resolved_repo = repo_slug or self.repo_name_with_owner()
        result = self._run(
            [
                "gh",
                "api",
                "--method",
                "POST",
                f"repos/{resolved_repo}/pulls/{pr_number}/comments/{comment_id}/replies",
                "-f",
                f"body={body}",
            ],
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("GitHub CLI returned invalid JSON for the review-comment reply.") from exc
        if not isinstance(payload, dict):
            raise ValueError("GitHub CLI returned an unexpected reply payload.")
        url = payload.get("html_url")
        if not isinstance(url, str) or not url:
            raise ValueError("GitHub CLI reply payload did not include a reply URL.")
        return url

    def _run(self, argv: list[str]) -> CommandResult:
        """Execute one GitHub CLI command and raise on failure."""

        result = self._runner(argv, self._project_root)
        if result.returncode != 0:
            raise CommandExecutionError(result)
        return result


__all__ = [
    "CommandExecutionError",
    "CommandResult",
    "GitClient",
    "GitHubCliClient",
    "PullRequestComment",
    "run_command",
]
