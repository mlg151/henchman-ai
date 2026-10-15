"""Tier 4 git workflow CLI commands."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

import click

from henchman.git.clients import CommandExecutionError
from henchman.git.workflow import (
    BranchInfo,
    BranchManager,
    BranchOperation,
    CommitAssistant,
    CommitSuggestion,
    PullRequestWorkflow,
    PullRequestWorkflowResult,
)


@runtime_checkable
class _CommitAssistantProtocol(Protocol):
    """Protocol for commit-message generation services."""

    def suggest(self, *, staged_only: bool = True) -> CommitSuggestion:
        """Return a generated commit suggestion."""


@runtime_checkable
class _BranchManagerProtocol(Protocol):
    """Protocol for branch management services."""

    def list(self) -> tuple[BranchInfo, ...]:
        """Return branch entries."""

    def create(
        self,
        name: str,
        *,
        switch: bool = False,
        start_point: str | None = None,
    ) -> BranchOperation:
        """Create one branch."""

    def switch(self, name: str) -> BranchOperation:
        """Switch to one branch."""


@runtime_checkable
class _WorkflowProtocol(Protocol):
    """Protocol for commit/push/PR workflow services."""

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
        """Run the workflow."""


CommitAssistantFactory = Callable[..., _CommitAssistantProtocol]
BranchManagerFactory = Callable[..., _BranchManagerProtocol]
WorkflowFactory = Callable[..., _WorkflowProtocol]


def create_commit_command(
    *,
    project_root: Path | None = None,
    commit_assistant_factory: CommitAssistantFactory | None = None,
) -> click.Command:
    """Create the `commit` command."""

    factory = commit_assistant_factory or CommitAssistant

    @click.command(name="commit", help="Generate an AI-assisted commit message suggestion.")
    @click.option(
        "--working-tree",
        is_flag=True,
        default=False,
        help="Generate the suggestion from unstaged working-tree changes instead of staged ones.",
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the commit suggestion as text or JSON.",
    )
    def _commit_command(working_tree: bool, output_format: str) -> None:
        assistant = factory(project_root=project_root)
        try:
            suggestion = assistant.suggest(staged_only=not working_tree)
        except (CommandExecutionError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_commit_suggestion(suggestion, output_format=output_format), nl=False)

    return _commit_command


def create_branch_command(
    *,
    project_root: Path | None = None,
    branch_manager_factory: BranchManagerFactory | None = None,
) -> click.Group:
    """Create the `branch` command group."""

    factory = branch_manager_factory or BranchManager

    @click.group(
        name="branch",
        help="Manage local git branches.",
        invoke_without_command=True,
    )
    @click.pass_context
    def branch_command(ctx: click.Context) -> None:
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @branch_command.command(name="list", help="List local branches.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render branch data as text or JSON.",
    )
    def list_command(output_format: str) -> None:
        manager = factory(project_root=project_root)
        try:
            branches = manager.list()
        except CommandExecutionError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_branch_list(branches, output_format=output_format), nl=False)

    @branch_command.command(name="create", help="Create a local branch.")
    @click.argument("name")
    @click.option("--switch", "switch_to_branch", is_flag=True, default=False, help="Switch to the new branch immediately.")
    @click.option("--start-point", default=None, help="Optional start point for the new branch.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the branch operation as text or JSON.",
    )
    def create_command(name: str, switch_to_branch: bool, start_point: str | None, output_format: str) -> None:
        manager = factory(project_root=project_root)
        try:
            operation = manager.create(name, switch=switch_to_branch, start_point=start_point)
        except CommandExecutionError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_branch_operation(operation, output_format=output_format), nl=False)

    @branch_command.command(name="switch", help="Switch to a local branch.")
    @click.argument("name")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the branch operation as text or JSON.",
    )
    def switch_command(name: str, output_format: str) -> None:
        manager = factory(project_root=project_root)
        try:
            operation = manager.switch(name)
        except CommandExecutionError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_branch_operation(operation, output_format=output_format), nl=False)

    return branch_command


def create_commit_push_pr_command(
    *,
    project_root: Path | None = None,
    workflow_factory: WorkflowFactory | None = None,
) -> click.Command:
    """Create the `commit-push-pr` command."""

    factory = workflow_factory or PullRequestWorkflow

    @click.command(name="commit-push-pr", help="Commit changes, push the branch, and create a pull request.")
    @click.option("--message", default=None, help="Explicit commit message to use.")
    @click.option("--title", default=None, help="Explicit pull request title.")
    @click.option("--body", default=None, help="Explicit pull request body.")
    @click.option("--stage-all", is_flag=True, default=False, help="Stage all tracked and untracked changes before committing.")
    @click.option("--fill", is_flag=True, default=False, help="Let the GitHub CLI fill PR metadata from commits.")
    @click.option("--draft", is_flag=True, default=False, help="Create the pull request as a draft.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the workflow result as text or JSON.",
    )
    def _workflow_command(
        message: str | None,
        title: str | None,
        body: str | None,
        stage_all: bool,
        fill: bool,
        draft: bool,
        output_format: str,
    ) -> None:
        workflow = factory(project_root=project_root)
        try:
            result = workflow.run(
                message=message,
                title=title,
                body=body,
                stage_all=stage_all,
                fill=fill,
                draft=draft,
            )
        except (CommandExecutionError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_workflow_result(result, output_format=output_format), nl=False)

    return _workflow_command


def _render_commit_suggestion(suggestion: CommitSuggestion, *, output_format: str) -> str:
    """Render one commit suggestion."""

    if output_format == "json":
        return json.dumps(suggestion.to_dict(), sort_keys=True)
    lines = [
        f"Suggested commit message: {suggestion.message}",
        f"Type: {suggestion.commit_type}",
    ]
    if suggestion.scope is not None:
        lines.append(f"Scope: {suggestion.scope}")
    lines.append(f"Summary: {suggestion.summary}")
    lines.append(f"Files: {', '.join(suggestion.files)}")
    return "\n".join(lines) + "\n"


def _render_branch_list(branches: tuple[BranchInfo, ...], *, output_format: str) -> str:
    """Render a branch listing."""

    if output_format == "json":
        return json.dumps([branch.to_dict() for branch in branches], sort_keys=True)
    if not branches:
        return "No branches found.\n"
    lines = ["Branches:"]
    for branch in branches:
        prefix = "*" if branch.is_current else " "
        lines.append(f"{prefix} {branch.name}")
    return "\n".join(lines) + "\n"


def _render_branch_operation(operation: BranchOperation, *, output_format: str) -> str:
    """Render a branch create or switch result."""

    if output_format == "json":
        return json.dumps(operation.to_dict(), sort_keys=True)
    if operation.action == "create":
        return f"Created branch {operation.branch}\n"
    return f"Switched to branch {operation.current_branch}\n"


def _render_workflow_result(result: PullRequestWorkflowResult, *, output_format: str) -> str:
    """Render the commit-push-pr workflow result."""

    if output_format == "json":
        return json.dumps(result.to_dict(), sort_keys=True)
    return (
        f"Commit message: {result.commit_message}\n"
        f"Branch: {result.branch}\n"
        f"Pull request: {result.pull_request_url}\n"
    )


__all__ = [
    "create_branch_command",
    "create_commit_command",
    "create_commit_push_pr_command",
    "register_git_commands",
]


def register_git_commands(cli: click.Group) -> None:
    """Register git workflow commands on a root click group.

    Args:
        cli: Root click group that should expose the git commands.
    """
    cli.add_command(create_commit_command())
    cli.add_command(create_branch_command())
    cli.add_command(create_commit_push_pr_command())
