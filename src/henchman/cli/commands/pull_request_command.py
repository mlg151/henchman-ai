"""Tier 4 pull-request CLI commands."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

import click

from henchman.git.clients import CommandExecutionError
from henchman.git.github_app import GitHubAppInstallRecord, GitHubAppService
from henchman.git.review import (
    AutofixReport,
    AutofixService,
    CommentDraft,
    CommentManager,
    CommentReplyResult,
    PullRequestReviewer,
    ReviewReport,
)


@runtime_checkable
class _ReviewerProtocol(Protocol):
    """Protocol for review services."""

    def review(
        self,
        *,
        pr_number: int | None = None,
        mode: str = "general",
        refresh: bool = False,
    ) -> ReviewReport:
        """Return a review report."""


@runtime_checkable
class _CommentManagerProtocol(Protocol):
    """Protocol for comment draft/reply services."""

    def generate(self, *, pr_number: int) -> tuple[CommentDraft, ...]:
        """Generate draft replies."""

    def respond(self, *, pr_number: int, comment_id: int, body: str) -> CommentReplyResult:
        """Send one reply."""


@runtime_checkable
class _AutofixServiceProtocol(Protocol):
    """Protocol for autofix services."""

    def autofix(
        self,
        *,
        pr_number: int | None = None,
        refresh: bool = False,
        apply: bool = False,
    ) -> AutofixReport:
        """Return an autofix report."""


@runtime_checkable
class _GitHubAppServiceProtocol(Protocol):
    """Protocol for GitHub App setup services."""

    def install(
        self,
        *,
        app_url: str,
        repo_slug: str | None = None,
        installation_id: int | None = None,
        webhook_secret_env: str = "HENCHMAN_GITHUB_WEBHOOK_SECRET",
        open_browser: bool = False,
    ) -> GitHubAppInstallRecord:
        """Persist one app installation record."""


ReviewerFactory = Callable[..., _ReviewerProtocol]
CommentManagerFactory = Callable[..., _CommentManagerProtocol]
AutofixServiceFactory = Callable[..., _AutofixServiceProtocol]
GitHubAppServiceFactory = Callable[..., _GitHubAppServiceProtocol]


def create_review_command(
    *,
    project_root: Path | None = None,
    reviewer_factory: ReviewerFactory | None = None,
) -> click.Command:
    """Create the `review` command."""

    factory = cast(ReviewerFactory, reviewer_factory or PullRequestReviewer)
    return _create_review_like_command(
        name="review",
        help_text="Review the current branch or pull request diff.",
        mode="general",
        project_root=project_root,
        reviewer_factory=factory,
    )


def create_security_review_command(
    *,
    project_root: Path | None = None,
    reviewer_factory: ReviewerFactory | None = None,
) -> click.Command:
    """Create the `security-review` command."""

    factory = cast(ReviewerFactory, reviewer_factory or PullRequestReviewer)
    return _create_review_like_command(
        name="security-review",
        help_text="Run a security-focused review on the current branch or pull request diff.",
        mode="security",
        project_root=project_root,
        reviewer_factory=factory,
    )


def create_pr_comments_command(
    *,
    project_root: Path | None = None,
    comment_manager_factory: CommentManagerFactory | None = None,
) -> click.Group:
    """Create the `pr_comments` command group."""

    factory = comment_manager_factory or CommentManager

    @click.group(
        name="pr_comments",
        help="Generate and send pull-request review comment replies.",
        invoke_without_command=True,
    )
    @click.pass_context
    def pr_comments_command(ctx: click.Context) -> None:
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @pr_comments_command.command(name="generate", help="Generate reply drafts for PR review comments.")
    @click.option("--pr", "pr_number", type=int, required=True, help="Pull request number to inspect.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render drafted replies as text or JSON.",
    )
    def generate_command(pr_number: int, output_format: str) -> None:
        manager = factory(project_root=project_root)
        try:
            drafts = manager.generate(pr_number=pr_number)
        except (CommandExecutionError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_comment_drafts(drafts, output_format=output_format), nl=False)

    @pr_comments_command.command(name="respond", help="Send one reply to a PR review comment.")
    @click.option("--pr", "pr_number", type=int, required=True, help="Pull request number that owns the comment.")
    @click.option("--comment-id", type=int, required=True, help="Review comment ID to reply to.")
    @click.option("--body", required=True, help="Reply body to post.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the reply result as text or JSON.",
    )
    def respond_command(
        pr_number: int,
        comment_id: int,
        body: str,
        output_format: str,
    ) -> None:
        manager = factory(project_root=project_root)
        try:
            reply = manager.respond(pr_number=pr_number, comment_id=comment_id, body=body)
        except (CommandExecutionError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_comment_reply(reply, output_format=output_format), nl=False)

    return pr_comments_command


def create_autofix_pr_command(
    *,
    project_root: Path | None = None,
    autofix_service_factory: AutofixServiceFactory | None = None,
) -> click.Command:
    """Create the `autofix-pr` command."""

    factory = autofix_service_factory or AutofixService

    @click.command(name="autofix-pr", help="Apply safe autofixes for review findings.")
    @click.option("--pr", "pr_number", type=int, default=None, help="Optional pull request number to inspect.")
    @click.option("--refresh", is_flag=True, default=False, help="Refresh a cached PR diff before analyzing it.")
    @click.option("--apply", is_flag=True, default=False, help="Apply supported fixes to local files.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the autofix report as text or JSON.",
    )
    def _autofix_command(
        pr_number: int | None,
        refresh: bool,
        apply: bool,
        output_format: str,
    ) -> None:
        service = factory(project_root=project_root)
        try:
            report = service.autofix(pr_number=pr_number, refresh=refresh, apply=apply)
        except (CommandExecutionError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_autofix_report(report, output_format=output_format), nl=False)

    return _autofix_command


def create_install_github_app_command(
    *,
    project_root: Path | None = None,
    github_app_service_factory: GitHubAppServiceFactory | None = None,
) -> click.Command:
    """Create the `install-github-app` command."""

    factory = github_app_service_factory or GitHubAppService

    @click.command(name="install-github-app", help="Persist local GitHub App setup metadata.")
    @click.option("--app-url", required=True, help="GitHub App installation URL.")
    @click.option("--repo", "repo_slug", default=None, help="Optional owner/repo for the installation record.")
    @click.option("--installation-id", type=int, default=None, help="Known GitHub App installation ID, when available.")
    @click.option(
        "--webhook-secret-env",
        default="HENCHMAN_GITHUB_WEBHOOK_SECRET",
        show_default=True,
        help="Environment variable name that stores the webhook secret.",
    )
    @click.option("--open", "open_browser", is_flag=True, default=False, help="Open the install URL in a browser.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the installation record as text or JSON.",
    )
    def _install_command(
        app_url: str,
        repo_slug: str | None,
        installation_id: int | None,
        webhook_secret_env: str,
        open_browser: bool,
        output_format: str,
    ) -> None:
        service = factory(project_root=project_root)
        try:
            record = service.install(
                app_url=app_url,
                repo_slug=repo_slug,
                installation_id=installation_id,
                webhook_secret_env=webhook_secret_env,
                open_browser=open_browser,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_install_record(record, output_format=output_format), nl=False)

    return _install_command


def _create_review_like_command(
    *,
    name: str,
    help_text: str,
    mode: str,
    project_root: Path | None,
    reviewer_factory: ReviewerFactory,
) -> click.Command:
    """Create one review-like command with shared options and rendering."""

    @click.command(name=name, help=help_text)
    @click.option("--pr", "pr_number", type=int, default=None, help="Optional pull request number to review.")
    @click.option("--refresh", is_flag=True, default=False, help="Refresh a cached PR diff before reviewing it.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the review report as text or JSON.",
    )
    def _review_command(pr_number: int | None, refresh: bool, output_format: str) -> None:
        reviewer = reviewer_factory(project_root=project_root)
        try:
            report = reviewer.review(pr_number=pr_number, mode=mode, refresh=refresh)
        except (CommandExecutionError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_review_report(report, output_format=output_format), nl=False)

    return _review_command


def _render_review_report(report: ReviewReport, *, output_format: str) -> str:
    """Render a review report."""

    if output_format == "json":
        return json.dumps(report.to_dict(), sort_keys=True)
    lines = [
        f"Mode: {report.mode}",
        f"Target: {report.target}",
        report.summary,
    ]
    for finding in report.findings:
        location = finding.file_path
        if finding.line_number is not None:
            location = f"{location}:{finding.line_number}"
        lines.append(f"- [{finding.severity}] {location}: {finding.message}")
    return "\n".join(lines) + "\n"


def _render_comment_drafts(drafts: tuple[CommentDraft, ...], *, output_format: str) -> str:
    """Render generated comment drafts."""

    if output_format == "json":
        return json.dumps([draft.to_dict() for draft in drafts], sort_keys=True)
    if not drafts:
        return "No review comments found.\n"
    lines = ["Draft replies:"]
    for draft in drafts:
        path_fragment = f" ({draft.path})" if draft.path else ""
        lines.append(f"- Comment {draft.comment_id}{path_fragment}: {draft.draft_reply}")
    return "\n".join(lines) + "\n"


def _render_comment_reply(reply: CommentReplyResult, *, output_format: str) -> str:
    """Render a posted comment reply."""

    if output_format == "json":
        return json.dumps(reply.to_dict(), sort_keys=True)
    return f"Posted reply to comment {reply.comment_id}: {reply.reply_url}\n"


def _render_autofix_report(report: AutofixReport, *, output_format: str) -> str:
    """Render an autofix report."""

    if output_format == "json":
        return json.dumps(report.to_dict(), sort_keys=True)
    lines = [
        f"Applied fixes: {report.applied_count}",
        f"Skipped fixes: {report.skipped_count}",
    ]
    for change in report.changes:
        status = "applied" if change.applied else "skipped"
        location = change.file_path
        if change.line_number is not None:
            location = f"{location}:{change.line_number}"
        lines.append(f"- {status} {change.finding_code} at {location}: {change.description}")
    return "\n".join(lines) + "\n"


def _render_install_record(record: GitHubAppInstallRecord, *, output_format: str) -> str:
    """Render a GitHub App installation record."""

    if output_format == "json":
        return json.dumps(record.to_dict(), sort_keys=True)
    lines = [
        f"App URL: {record.app_url}",
        f"Repository: {record.repo_slug or 'not set'}",
        f"Webhook secret env: {record.webhook_secret_env}",
        f"Metadata path: {record.metadata_path}",
    ]
    if record.installation_id is not None:
        lines.append(f"Installation ID: {record.installation_id}")
    return "\n".join(lines) + "\n"


__all__ = [
    "create_autofix_pr_command",
    "create_install_github_app_command",
    "create_pr_comments_command",
    "create_review_command",
    "create_security_review_command",
    "register_pull_request_commands",
]


def register_pull_request_commands(cli: click.Group) -> None:
    """Register pull request workflow commands on a root click group.

    Args:
        cli: Root click group that should expose the pull request commands.
    """
    cli.add_command(create_review_command())
    cli.add_command(create_security_review_command())
    cli.add_command(create_pr_comments_command())
    cli.add_command(create_autofix_pr_command())
    cli.add_command(create_install_github_app_command())
