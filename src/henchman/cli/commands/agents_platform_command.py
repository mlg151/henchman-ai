"""Root CLI command for agent definition management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio
import click

from henchman.agents.catalog import AgentCatalog
from henchman.agents.platform_manager import (
    AgentPlatformManager,
    AgentRegistryInstallError,
)
from henchman.config.paths import resolve_project_settings_path


def _get_platform_data_dir(project_root: Path | None = None) -> Path:
    """Resolve the platform data directory lazily at invocation time.

    Args:
        project_root: Optional explicit project root.

    Returns:
        Path to the platform data directory.
    """
    resolved = project_root or Path.cwd()
    return resolve_project_settings_path(resolved) / "agents"


def create_agents_platform_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root `agents-platform` command group."""

    @click.group(
        name="agents-platform",
        help="Manage local agent definitions, guarded registry installs, and local publishing.",
        invoke_without_command=True,
    )
    @click.pass_context
    def agents_platform_command(ctx: click.Context) -> None:
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @agents_platform_command.command(name="list", help="List discovered agent definitions.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render discovered agents as text or JSON.",
    )
    def list_command(output_format: str) -> None:
        resolved = project_root or Path.cwd()
        catalog = AgentCatalog(project_root=resolved)
        payload = [
            {
                "role": definition.role,
                "name": definition.name,
                "version": definition.version,
                "description": definition.description,
                "source_kind": definition.source_kind,
                "source_path": str(definition.source_path),
            }
            for definition in catalog.list_agents()
        ]
        click.echo(_render_list_payload(payload, output_format=output_format), nl=False)

    @agents_platform_command.command(name="show", help="Show one discovered agent definition.")
    @click.argument("role")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the agent definition as text or JSON.",
    )
    def show_command(role: str, output_format: str) -> None:
        resolved = project_root or Path.cwd()
        catalog = AgentCatalog(project_root=resolved)
        definition = catalog.get(role)
        if definition is None:
            raise click.ClickException(f"Unknown agent definition: {role}")
        payload = {
            "role": definition.role,
            "name": definition.name,
            "version": definition.version,
            "description": definition.description,
            "tools": list(definition.config.tools),
            "system_prompt": definition.config.system_prompt,
            "source_kind": definition.source_kind,
            "source_path": str(definition.source_path),
        }
        click.echo(_render_show_payload(payload, output_format=output_format), nl=False)

    @agents_platform_command.command(
        name="install",
        help="Attempt one registry-backed install when registry metadata is available.",
    )
    @click.argument("role")
    @click.option("--version", default=None, help="Install a specific agent version.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the install result as text or JSON.",
    )
    def install_command(role: str, version: str | None, output_format: str) -> None:
        async def _install_payload() -> dict[str, Any]:
            manager = AgentPlatformManager(data_dir=_get_platform_data_dir(project_root))
            await manager.initialize()
            try:
                installation = await manager.install_agent(role, version)
                return {
                    "role": installation.definition.role,
                    "version": installation.installed_version,
                    "description": installation.definition.description,
                }
            finally:
                await manager.close()

        try:
            payload = anyio.run(_install_payload)
        except (AgentRegistryInstallError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(_render_install_payload(payload, output_format=output_format), nl=False)

    @agents_platform_command.command(name="remove", help="Remove one installed agent definition.")
    @click.argument("role")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the removal result as text or JSON.",
    )
    def remove_command(role: str, output_format: str) -> None:
        async def _remove_payload() -> dict[str, Any]:
            manager = AgentPlatformManager(data_dir=_get_platform_data_dir(project_root))
            await manager.initialize()
            try:
                await manager.uninstall_agent(role)
                return {"role": role}
            finally:
                await manager.close()

        payload = anyio.run(_remove_payload)
        click.echo(_render_remove_payload(payload, output_format=output_format), nl=False)

    @agents_platform_command.command(name="publish", help="Publish one local agent spec.")
    @click.argument(
        "spec_path",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the publication result as text or JSON.",
    )
    def publish_command(spec_path: Path, output_format: str) -> None:
        async def _publish_payload() -> dict[str, Any]:
            manager = AgentPlatformManager(data_dir=_get_platform_data_dir(project_root))
            await manager.initialize()
            try:
                publication = await manager.publish_agent(spec_path)
                return {
                    "role": publication.definition.role,
                    "version": publication.version,
                    "publication_path": publication.publication_path,
                }
            finally:
                await manager.close()

        payload = anyio.run(_publish_payload)
        click.echo(_render_publish_payload(payload, output_format=output_format), nl=False)

    return agents_platform_command


def _render_list_payload(payload: list[dict[str, Any]], *, output_format: str) -> str:
    """Render discovered agent definition payloads."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)

    if not payload:
        return "No agent definitions found.\n"

    lines = ["Available agents:"]
    for agent in payload:
        lines.append(
            f"- {agent['role']} {agent['version']} ({agent['source_kind']}): {agent['description']}",
        )
    return "\n".join(lines) + "\n"


def _render_show_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render one discovered agent definition payload."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)

    lines = [
        f"Role: {payload['role']}",
        f"Name: {payload['name']}",
        f"Version: {payload['version']}",
        f"Source: {payload['source_kind']}",
        f"Description: {payload['description']}",
    ]
    if payload["tools"]:
        lines.append(f"Tools: {', '.join(payload['tools'])}")
    if payload["system_prompt"]:
        lines.extend(["System prompt:", str(payload["system_prompt"])])
    return "\n".join(lines) + "\n"


def _render_install_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render one agent installation payload."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)
    return (
        f"Installed agent {payload['role']} {payload['version']}"
        f" - {payload['description']}\n"
    )


def _render_remove_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render one agent removal payload."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)
    return f"Removed agent {payload['role']}\n"


def _render_publish_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render one local agent publication payload."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)
    return (
        f"Published agent {payload['role']} {payload['version']}"
        f" -> {payload['publication_path']}\n"
    )


def register_agents_platform_command(
    cli: click.Group,
    *,
    project_root: Path | None = None,
) -> click.Command:
    """Register the agents-platform command on a root click group.

    Args:
        cli: Root click group that should expose the command.
        project_root: Optional project root for deterministic tests.

    Returns:
        The command instance added to ``cli``.
    """
    command = create_agents_platform_command(project_root=project_root)
    cli.add_command(command)
    return command
