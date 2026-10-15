"""Git workflow services used by Tier 4 CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from henchman.git.clients import GitClient, GitHubCliClient


@dataclass(frozen=True, slots=True)
class CommitSuggestion:
    """A generated commit-message suggestion."""

    message: str
    commit_type: str
    scope: str | None
    summary: str
    files: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "message": self.message,
            "commit_type": self.commit_type,
            "scope": self.scope,
            "summary": self.summary,
            "files": list(self.files),
        }


@dataclass(frozen=True, slots=True)
class BranchInfo:
    """One git branch entry."""

    name: str
    is_current: bool

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {"name": self.name, "is_current": self.is_current}


@dataclass(frozen=True, slots=True)
class BranchOperation:
    """Result from a branch create or switch operation."""

    action: str
    branch: str
    current_branch: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "action": self.action,
            "branch": self.branch,
            "current_branch": self.current_branch,
        }


@dataclass(frozen=True, slots=True)
class PullRequestWorkflowResult:
    """Result from the commit-push-pr workflow."""

    commit_message: str
    branch: str
    pull_request_url: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "commit_message": self.commit_message,
            "branch": self.branch,
            "pull_request_url": self.pull_request_url,
        }


class CommitAssistant:
    """Generate deterministic commit-message suggestions from changed files."""

    def __init__(self, project_root: Path | None = None, *, git_client: GitClient | None = None) -> None:
        """Initialize the assistant."""

        self._git_client = git_client or GitClient(project_root=project_root)

    def suggest(self, *, staged_only: bool = True) -> CommitSuggestion:
        """Return a commit suggestion for the current workspace."""

        files = self._git_client.changed_files(staged_only=staged_only)
        if not files:
            raise ValueError("No changed files were found for commit message generation.")

        commit_type = _infer_commit_type(files)
        scope = _infer_scope(files)
        summary = _build_summary(files, commit_type=commit_type)
        scope_fragment = f"({scope})" if scope else ""
        return CommitSuggestion(
            message=f"{commit_type}{scope_fragment}: {summary}",
            commit_type=commit_type,
            scope=scope,
            summary=summary,
            files=files,
        )


class BranchManager:
    """Manage local git branches."""

    def __init__(self, project_root: Path | None = None, *, git_client: GitClient | None = None) -> None:
        """Initialize the manager."""

        self._git_client = git_client or GitClient(project_root=project_root)

    def list(self) -> tuple[BranchInfo, ...]:
        """Return available local branches."""

        return tuple(
            BranchInfo(name=name, is_current=is_current)
            for name, is_current in self._git_client.list_branches()
        )

    def create(
        self,
        name: str,
        *,
        switch: bool = False,
        start_point: str | None = None,
    ) -> BranchOperation:
        """Create one branch."""

        current_branch = self._git_client.create_branch(
            name,
            switch=switch,
            start_point=start_point,
        )
        return BranchOperation(action="create", branch=name, current_branch=current_branch)

    def switch(self, name: str) -> BranchOperation:
        """Switch to one branch."""

        current_branch = self._git_client.switch_branch(name)
        return BranchOperation(action="switch", branch=name, current_branch=current_branch)


class PullRequestWorkflow:
    """Commit, push, and open a pull request in one flow."""

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        git_client: GitClient | None = None,
        github_client: GitHubCliClient | None = None,
        commit_assistant: CommitAssistant | None = None,
    ) -> None:
        """Initialize the workflow."""

        self._git_client = git_client or GitClient(project_root=project_root)
        self._github_client = github_client or GitHubCliClient(project_root=project_root)
        self._commit_assistant = commit_assistant or CommitAssistant(
            project_root=project_root,
            git_client=self._git_client,
        )

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
        """Run the commit, push, and PR-create workflow."""

        resolved_message = message or self._commit_assistant.suggest(staged_only=not stage_all).message
        self._git_client.commit(resolved_message, stage_all=stage_all)
        branch = self._git_client.push_current_branch()
        resolved_title = title or resolved_message
        resolved_body = body if body is not None else _default_pull_request_body(resolved_message)
        pull_request_url = self._github_client.create_pull_request(
            title=resolved_title,
            body=resolved_body,
            fill=fill,
            draft=draft,
        )
        return PullRequestWorkflowResult(
            commit_message=resolved_message,
            branch=branch,
            pull_request_url=pull_request_url,
        )


def _infer_commit_type(files: tuple[str, ...]) -> str:
    """Infer a conventional-commit type from the changed files."""

    if all(_is_docs_file(file_path) for file_path in files):
        return "docs"
    if all(_is_test_file(file_path) for file_path in files):
        return "test"
    if any(file_path.startswith("src/") for file_path in files):
        return "feat"
    return "chore"


def _infer_scope(files: tuple[str, ...]) -> str | None:
    """Infer a conventional-commit scope from the changed files."""

    if all(file_path.startswith("src/henchman/cli/") or _is_test_file(file_path) for file_path in files):
        return "cli"
    if all(file_path.startswith("src/henchman/tools/") or _is_test_file(file_path) for file_path in files):
        return "tools"
    if all(_is_docs_file(file_path) for file_path in files):
        return None
    return None


def _build_summary(files: tuple[str, ...], *, commit_type: str) -> str:
    """Build a terse summary fragment from the changed files."""

    subjects = [_humanize_subject(file_path) for file_path in files]
    unique_subjects = tuple(dict.fromkeys(subjects))
    action = "update" if commit_type in {"docs", "chore"} else "add"
    return f"{action} {_join_subjects(unique_subjects)}"


def _humanize_subject(file_path: str) -> str:
    """Convert one path into a short summary fragment."""

    path = Path(file_path)
    stem = path.stem
    if stem == "__init__":
        stem = path.parent.name
    for prefix in ("test_",):
        if stem.startswith(prefix):
            stem = stem.removeprefix(prefix)
    for suffix in ("_command", "_service", "_manager"):
        if stem.endswith(suffix):
            stem = stem.removesuffix(suffix)
    return stem.replace("_", " ").replace("-", " ").casefold()


def _join_subjects(subjects: tuple[str, ...]) -> str:
    """Join subject fragments into a compact natural-language list."""

    if len(subjects) == 1:
        return subjects[0]
    if len(subjects) == 2:
        return f"{subjects[0]} and {subjects[1]}"
    return f"{', '.join(subjects[:-1])}, and {subjects[-1]}"


def _default_pull_request_body(commit_message: str) -> str:
    """Build a simple default PR body."""

    return f"## Summary\n- {commit_message}\n"


def _is_docs_file(file_path: str) -> bool:
    """Return whether the path is documentation-oriented."""

    return file_path.startswith("docs/") or file_path.endswith((".md", ".rst", ".txt"))


def _is_test_file(file_path: str) -> bool:
    """Return whether the path looks like a test file."""

    return file_path.startswith("tests/") or Path(file_path).stem.startswith("test_")


__all__ = [
    "BranchInfo",
    "BranchManager",
    "BranchOperation",
    "CommitAssistant",
    "CommitSuggestion",
    "PullRequestWorkflow",
    "PullRequestWorkflowResult",
]
