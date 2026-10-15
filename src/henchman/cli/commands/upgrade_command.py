"""Guided self-upgrade command for conservative Tier 1 upgrades."""

from __future__ import annotations

import subprocess

import click

from henchman.cli.system_info import get_system_info
from henchman.cli.update_check import build_update_plan
from henchman.tools.security import sanitize_error_message


def _render_update_summary(*, summary: str, failure_code: str | None) -> str:
    """Render the upgrade summary with an optional stable failure code."""

    if failure_code is None:
        return summary
    return f"{failure_code}: {summary}"


def _run_update_command(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    """Execute a pre-built argv command without invoking a shell."""

    return subprocess.run(command, check=False, capture_output=True, text=True)


def _build_failure_excerpt(completed_process: subprocess.CompletedProcess[str]) -> str:
    """Build a sanitized stdout/stderr excerpt for a failed upgrade command."""

    excerpts: list[str] = []
    if completed_process.stderr:
        excerpts.append(f"stderr: {sanitize_error_message(completed_process.stderr)}")
    if completed_process.stdout:
        excerpts.append(f"stdout: {sanitize_error_message(completed_process.stdout)}")
    if not excerpts:
        return ""
    return f" Output excerpt: {'; '.join(excerpts)}"


@click.command(name="upgrade")
@click.option(
    "--run",
    "should_run",
    is_flag=True,
    help="Execute the detected upgrade command after confirmation.",
)
def upgrade_command(*, should_run: bool) -> None:
    """Explain or run the supported self-upgrade command for this install."""

    system_info = get_system_info()
    update_plan = build_update_plan(system_info)

    click.echo(
        _render_update_summary(
            summary=update_plan.summary,
            failure_code=update_plan.failure_code,
        )
    )
    if update_plan.rendered_command:
        click.echo(f"Recommended command: {update_plan.rendered_command}")

    if not update_plan.can_self_update:
        click.echo("Manual upgrade guidance: reinstall with the original package manager.")
        return

    if not should_run:
        click.echo("Re-run with --run to execute this command.")
        return

    if not click.confirm("Run this command now?", default=False):
        click.echo("Upgrade cancelled.")
        return

    try:
        completed_process = _run_update_command(update_plan.command)
    except OSError as error:
        sanitized_error = sanitize_error_message(error)
        raise click.ClickException(
            f"Failed to execute upgrade command: {sanitized_error}"
        ) from error

    if completed_process.returncode != 0:
        failure_excerpt = _build_failure_excerpt(completed_process)
        raise click.ClickException(
            f"Upgrade command failed with exit code {completed_process.returncode}."
            f"{failure_excerpt}"
        )

    click.echo("Upgrade command completed successfully.")
