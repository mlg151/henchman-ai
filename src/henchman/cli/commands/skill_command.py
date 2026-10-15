"""Root CLI command for compatible skill discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from henchman.skills import SkillCatalog


def _resolve_project_root(project_root: Path | None = None) -> Path:
    """Resolve the project root, falling back to cwd at invocation time.

    Args:
        project_root: Optional explicit project root.

    Returns:
        Resolved project root path.
    """
    return project_root or Path.cwd()


def create_skill_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root `skill` command group."""

    @click.group(
        name="skill",
        help=(
            "Discover and inspect compatible local skills from Henchman, Claude, "
            "Gemini, and GitHub Copilot. This surface can list and inspect metadata "
            "only; it does not execute skills."
        ),
        invoke_without_command=True,
    )
    @click.pass_context
    def skill_command(ctx: click.Context) -> None:
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @skill_command.command(name="list", help="List discovered local skills.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the skills list as text or JSON.",
    )
    def list_command(output_format: str) -> None:
        catalog = SkillCatalog(project_root=_resolve_project_root(project_root))
        skills = catalog.list_skills()
        payload = [
            {
                "name": skill.name,
                "description": skill.description,
                "source_kind": skill.source_kind,
                "source_path": str(skill.source_path),
            }
            for skill in skills
        ]
        click.echo(_render_list_payload(payload, output_format=output_format), nl=False)

    @skill_command.command(name="show", help="Show one discovered skill definition.")
    @click.argument("skill_name")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the skill as text or JSON.",
    )
    def show_command(skill_name: str, output_format: str) -> None:
        catalog = SkillCatalog(project_root=_resolve_project_root(project_root))
        skill = catalog.get(skill_name)
        if skill is None:
            raise click.ClickException(f"Unknown skill: {skill_name}")

        payload = {
            "name": skill.name,
            "description": skill.description,
            "instructions": skill.instructions,
            "source_kind": skill.source_kind,
            "source_path": str(skill.source_path),
        }
        click.echo(_render_skill_payload(payload, output_format=output_format), nl=False)

    return skill_command


def _render_list_payload(payload: list[dict[str, Any]], *, output_format: str) -> str:
    """Render the discovered skills list."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)

    if not payload:
        return "No compatible local skills found.\n"

    lines = ["Available skills (local discovery only):"]
    for skill in payload:
        description = skill["description"] or "No description."
        lines.append(f"- {skill['name']} ({skill['source_kind']}): {description}")
    return "\n".join(lines) + "\n"


def _render_skill_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render one discovered skill."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)

    lines = [
        f"Skill: {payload['name']}",
        f"Source: {payload['source_kind']}",
        "Mode: Metadata only (does not execute skills)",
    ]
    if payload["description"]:
        lines.append(f"Description: {payload['description']}")
    if payload["instructions"]:
        lines.extend(["Instructions:", payload["instructions"]])
    return "\n".join(lines) + "\n"


def register_skill_command(
    cli: click.Group,
    *,
    project_root: Path | None = None,
) -> click.Command:
    """Register the skill command group on a root click group.

    Args:
        cli: Root click group that should expose the skill command.
        project_root: Optional project root for deterministic tests.

    Returns:
        The command instance added to ``cli``.
    """
    command = create_skill_command(project_root=project_root)
    cli.add_command(command)
    return command
