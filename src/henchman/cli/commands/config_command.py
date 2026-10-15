"""Click command factories for the Tier 1 config command group."""

from __future__ import annotations

from pathlib import Path

import click

from henchman.cli.commands.config_view_command import (
    create_config_get_command,
    create_config_list_command,
    create_config_view_command,
)
from henchman.cli.commands.config_write_command import (
    create_config_export_command,
    create_config_import_command,
    create_config_set_command,
    create_config_unset_command,
)


def create_config_command(*, project_root: Path | None = None) -> click.Group:
    """Create the user-facing Tier 1 config command group.

    Args:
        project_root: Optional project root used to resolve project-local settings.

    Returns:
        A click group that routes config reads and writes to the lower-level slices.
    """

    @click.group(
        name="config",
        help="Inspect and edit key-based local configuration values.",
    )
    def config_command() -> None:
        """Tier 1 config command group."""

    config_command.add_command(create_config_view_command(project_root=project_root))
    config_command.add_command(create_config_get_command(project_root=project_root))
    config_command.add_command(create_config_list_command(project_root=project_root))
    config_command.add_command(create_config_set_command(project_root=project_root))
    config_command.add_command(create_config_unset_command(project_root=project_root))
    config_command.add_command(create_config_import_command(project_root=project_root))
    config_command.add_command(create_config_export_command(project_root=project_root))
    return config_command


def register_config_command(
    cli: click.Group,
    *,
    project_root: Path | None = None,
) -> click.Command:
    """Register the Tier 1 config command group on a root click group.

    Args:
        cli: Root click group that should expose the config command group.
        project_root: Optional project root used to resolve project-local settings.

    Returns:
        The command instance added to ``cli``.
    """
    command = create_config_command(project_root=project_root)
    cli.add_command(command)
    return command


__all__ = [
    "create_config_command",
    "register_config_command",
]
