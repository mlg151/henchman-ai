"""CLI commands for Tier 7 integration blueprint management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from henchman.integrations.blueprints import export_blueprint, list_blueprints


def _render_list_payload(payload: list[dict[str, Any]], *, output_format: str) -> str:
    """Render integration list payloads."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)

    if not payload:
        return "No integration export scaffolds available.\n"

    lines = ["Available integrations (export-only scaffolds):"]
    for item in payload:
        lines.append(f"- {item['slug']}: {item['description']}")
    return "\n".join(lines) + "\n"


def _render_export_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render one integration export payload."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)
    return (
        f"Exported {payload['slug']} scaffold to {payload['destination']}"
        f" ({len(payload['files'])} files)\n"
        "Export-only: this command writes local blueprint files and does not launch "
        "or configure a runtime.\n"
    )


def _create_surface_command(
    *,
    command_name: str,
    surface: str,
    help_text: str,
) -> click.Group:
    """Create one integration surface command group."""

    @click.group(
        name=command_name,
        help=help_text,
        invoke_without_command=True,
    )
    @click.pass_context
    def integration_command(ctx: click.Context) -> None:
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @integration_command.command(name="list", help="List bundled integration export scaffolds.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render integration targets as text or JSON.",
    )
    def list_command(output_format: str) -> None:
        payload = [
            {
                "slug": blueprint.slug,
                "name": blueprint.name,
                "description": blueprint.description,
            }
            for blueprint in list_blueprints(surface=surface)  # type: ignore[arg-type]
        ]
        click.echo(_render_list_payload(payload, output_format=output_format), nl=False)

    @integration_command.command(
        name="export",
        help="Export one bundled integration scaffold without launching a runtime.",
    )
    @click.argument("target")
    @click.argument("destination", type=click.Path(file_okay=False, path_type=Path))
    @click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Overwrite existing files in the destination.",
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the export result as text or JSON.",
    )
    def export_command(
        target: str,
        destination: Path,
        force: bool,
        output_format: str,
    ) -> None:
        blueprint = next(
            (item for item in list_blueprints(surface=surface) if item.slug == target),  # type: ignore[arg-type]
            None,
        )
        if blueprint is None:
            raise click.ClickException(f"Unknown {command_name} integration: {target}")

        written_paths = export_blueprint(target, destination, force=force)
        payload = {
            "slug": blueprint.slug,
            "destination": str(destination),
            "files": [
                str(path.relative_to(destination.resolve()))
                for path in written_paths
            ],
        }
        click.echo(_render_export_payload(payload, output_format=output_format), nl=False)

    return integration_command


def create_ide_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root `ide` command group."""

    del project_root
    return _create_surface_command(
        command_name="ide",
        surface="ide",
        help_text=(
            "List and export bundled IDE integration scaffolds. Export-only: this "
            "surface writes blueprint files and does not launch or configure runtimes."
        ),
    )


def create_desktop_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root `desktop` command group."""

    del project_root
    return _create_surface_command(
        command_name="desktop",
        surface="desktop",
        help_text=(
            "List and export bundled desktop integration scaffolds. Export-only: "
            "this surface writes blueprint files and does not launch or configure "
            "runtimes."
        ),
    )


def create_mobile_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root `mobile` command group."""

    del project_root
    return _create_surface_command(
        command_name="mobile",
        surface="mobile",
        help_text=(
            "List and export bundled mobile integration scaffolds. Export-only: "
            "this surface writes blueprint files and does not launch or configure "
            "runtimes."
        ),
    )


def create_chrome_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root `chrome` command group."""

    del project_root
    return _create_surface_command(
        command_name="chrome",
        surface="chrome",
        help_text=(
            "List and export bundled Chrome integration scaffolds. Export-only: "
            "this surface writes blueprint files and does not launch or configure "
            "runtimes."
        ),
    )


def register_integration_commands(
    cli: click.Group,
    *,
    project_root: Path | None = None,
) -> None:
    """Register integration/export commands on a root click group.

    Args:
        cli: Root click group that should expose the integration commands.
        project_root: Optional project root for deterministic tests.
    """
    cli.add_command(create_ide_command(project_root=project_root))
    cli.add_command(create_desktop_command(project_root=project_root))
    cli.add_command(create_mobile_command(project_root=project_root))
    cli.add_command(create_chrome_command(project_root=project_root))
