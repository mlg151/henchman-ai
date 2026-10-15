"""Root CLI command for marketplace-backed plugin management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio
import click

from henchman.extensions import PluginManager
from henchman.extensions.plugin_manager import (
    PluginMarketplaceUnavailableError,
    PluginRegistryLookupError,
)


def create_plugin_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root `plugin` command group."""

    del project_root

    @click.group(
        name="plugin",
        help=(
            "List and remove local plugins. Marketplace installs are unavailable "
            "in this build unless a real registry backend is configured."
        ),
        invoke_without_command=True,
    )
    @click.pass_context
    def plugin_command(ctx: click.Context) -> None:
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @plugin_command.command(name="list", help="List installed plugins.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render installed plugins as text or JSON.",
    )
    def list_command(output_format: str) -> None:
        async def _collect_payload() -> list[dict[str, Any]]:
            manager = PluginManager()
            await manager.initialize()
            try:
                return [
                    {
                        "name": installation.metadata.name,
                        "version": installation.installed_version,
                        "description": installation.metadata.description,
                        "enabled": installation.enabled,
                    }
                    for installation in manager.installed_plugins.values()
                ]
            finally:
                await manager.close()

        payload = anyio.run(_collect_payload)
        click.echo(_render_list_payload(payload, output_format=output_format), nl=False)

    @plugin_command.command(
        name="install",
        help=(
            "Install one plugin from the marketplace. This build only supports "
            "local list/remove flows unless registry metadata is configured."
        ),
    )
    @click.argument("plugin_name")
    @click.option("--version", default=None, help="Install a specific plugin version.")
    @click.option(
        "-y",
        "--yes",
        is_flag=True,
        default=False,
        help="Skip permission confirmation prompts.",
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the install result as text or JSON.",
    )
    def install_command(
        plugin_name: str,
        version: str | None,
        yes: bool,
        output_format: str,
    ) -> None:
        async def _install_payload() -> dict[str, Any]:
            manager = PluginManager()
            await manager.initialize()
            try:
                installation = await manager.install_plugin(
                    plugin_name=plugin_name,
                    version=version,
                    confirm_permissions=not yes,
                )
                return {
                    "name": installation.metadata.name,
                    "version": installation.installed_version,
                    "description": installation.metadata.description,
                    "enabled": installation.enabled,
                }
            finally:
                await manager.close()

        try:
            payload = anyio.run(_install_payload)
        except (
            OSError,
            PluginMarketplaceUnavailableError,
            PluginRegistryLookupError,
            ValueError,
        ) as error:
            raise click.ClickException(str(error)) from error
        click.echo(_render_install_payload(payload, output_format=output_format), nl=False)

    @plugin_command.command(name="remove", help="Remove one installed plugin.")
    @click.argument("plugin_name")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the removal result as text or JSON.",
    )
    def remove_command(plugin_name: str, output_format: str) -> None:
        async def _remove_payload() -> dict[str, Any]:
            manager = PluginManager()
            await manager.initialize()
            try:
                await manager.uninstall_plugin(plugin_name)
                return {"name": plugin_name, "operation": "remove"}
            finally:
                await manager.close()

        payload = anyio.run(_remove_payload)
        click.echo(_render_remove_payload(payload, output_format=output_format), nl=False)

    return plugin_command


def _render_list_payload(payload: list[dict[str, Any]], *, output_format: str) -> str:
    """Render installed plugin payloads."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)

    if not payload:
        return "No installed plugins.\n"

    lines = ["Installed plugins:"]
    for plugin in payload:
        lines.append(f"- {plugin['name']} {plugin['version']}: {plugin['description']}")
    return "\n".join(lines) + "\n"


def register_plugin_command(
    cli: click.Group,
    *,
    project_root: Path | None = None,
) -> click.Command:
    """Register the plugin command group on a root click group.

    Args:
        cli: Root click group that should expose the plugin command.
        project_root: Optional project root for deterministic tests.

    Returns:
        The command instance added to ``cli``.
    """
    command = create_plugin_command(project_root=project_root)
    cli.add_command(command)
    return command


def _render_install_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render one plugin installation payload."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)
    return (
        f"Installed plugin {payload['name']} {payload['version']}"
        f" - {payload['description']}\n"
    )


def _render_remove_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render one plugin removal payload."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)
    return f"Removed plugin {payload['name']}\n"
