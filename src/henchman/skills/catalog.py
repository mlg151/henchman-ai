"""Discover compatible skills across Henchman and external agent ecosystems."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    """Normalized skill metadata from any supported ecosystem."""

    name: str
    description: str
    instructions: str
    source_path: Path
    source_kind: str


class SkillCatalog:
    """Discover and resolve skills from compatible on-disk formats."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        home_dir: Path | None = None,
    ) -> None:
        """Initialize a skill catalog rooted at one project and one home directory."""

        self._project_root = project_root or Path.cwd()
        self._home_dir = home_dir or Path.home()

    def set_project_root(self, project_root: Path) -> None:
        """Update the project root used for discovery."""

        self._project_root = project_root

    def set_home_dir(self, home_dir: Path) -> None:
        """Update the home directory used for discovery."""

        self._home_dir = home_dir

    def list_skills(self) -> list[SkillDefinition]:
        """Return discovered skills sorted by name."""

        skills = self._discover_skills()
        return sorted(skills.values(), key=lambda skill: skill.name)

    def get(self, name: str) -> SkillDefinition | None:
        """Resolve one skill by name, case-insensitively."""

        return self._discover_skills().get(name.casefold())

    def _discover_skills(self) -> dict[str, SkillDefinition]:
        """Discover all supported skills, with project-local precedence."""

        skills: dict[str, SkillDefinition] = {}
        for definition in self._iter_discovered_skills():
            skills[definition.name.casefold()] = definition
        return skills

    def _iter_discovered_skills(self) -> list[SkillDefinition]:
        """Return skills in precedence order from lowest to highest."""

        discovered: list[SkillDefinition] = []
        discovered.extend(self._discover_gemini_commands(self._home_dir / ".gemini" / "commands"))
        discovered.extend(self._discover_markdown_commands(self._home_dir / ".claude" / "commands"))
        discovered.extend(self._discover_markdown_skills(self._home_dir / ".claude" / "skills", "claude_skill"))
        discovered.extend(self._discover_yaml_skills(self._home_dir / ".henchman" / "skills"))

        discovered.extend(
            self._discover_markdown_prompts(self._project_root / ".github" / "prompts")
        )
        discovered.extend(
            self._discover_markdown_skills(self._project_root / ".github" / "skills", "copilot_skill")
        )
        discovered.extend(self._discover_yaml_skills(self._project_root / "skills"))
        discovered.extend(self._discover_gemini_commands(self._project_root / ".gemini" / "commands"))
        discovered.extend(
            self._discover_markdown_commands(self._project_root / ".claude" / "commands")
        )
        discovered.extend(
            self._discover_markdown_skills(self._project_root / ".claude" / "skills", "claude_skill")
        )
        discovered.extend(self._discover_yaml_skills(self._project_root / ".henchman" / "skills"))
        return discovered

    def _discover_yaml_skills(self, directory: Path) -> list[SkillDefinition]:
        """Load native Henchman YAML skills from one directory tree."""

        definitions: list[SkillDefinition] = []
        if not directory.is_dir():
            return definitions

        for skill_file in sorted(directory.rglob("*.y*ml")):
            raw_payload = yaml.safe_load(skill_file.read_text(encoding="utf-8")) or {}
            if not isinstance(raw_payload, dict):
                continue

            name = str(raw_payload.get("name") or skill_file.stem)
            description = str(raw_payload.get("description") or "").strip()
            definitions.append(
                SkillDefinition(
                    name=name,
                    description=description,
                    instructions=_render_native_skill_instructions(raw_payload),
                    source_path=skill_file,
                    source_kind="henchman",
                )
            )
        return definitions

    def _discover_markdown_skills(self, directory: Path, source_kind: str) -> list[SkillDefinition]:
        """Load Markdown skills stored under `<root>/<name>/SKILL.md`."""

        definitions: list[SkillDefinition] = []
        if not directory.is_dir():
            return definitions

        for skill_file in sorted(directory.rglob("SKILL.md")):
            metadata, body = _parse_markdown_asset(skill_file.read_text(encoding="utf-8"))
            name = str(metadata.get("name") or skill_file.parent.name)
            description = str(metadata.get("description") or "").strip()
            definitions.append(
                SkillDefinition(
                    name=name,
                    description=description,
                    instructions=body,
                    source_path=skill_file,
                    source_kind=source_kind,
                )
            )
        return definitions

    def _discover_markdown_commands(self, directory: Path) -> list[SkillDefinition]:
        """Load Claude-style Markdown command files as reusable skills."""

        definitions: list[SkillDefinition] = []
        if not directory.is_dir():
            return definitions

        for command_file in sorted(directory.rglob("*.md")):
            metadata, body = _parse_markdown_asset(command_file.read_text(encoding="utf-8"))
            relative = command_file.relative_to(directory)
            name = str(metadata.get("name") or _name_from_relative_path(relative, suffixes=(".md",)))
            description = str(metadata.get("description") or "").strip()
            definitions.append(
                SkillDefinition(
                    name=name,
                    description=description,
                    instructions=body,
                    source_path=command_file,
                    source_kind="claude_command",
                )
            )
        return definitions

    def _discover_markdown_prompts(self, directory: Path) -> list[SkillDefinition]:
        """Load GitHub Copilot prompt files as reusable skills."""

        definitions: list[SkillDefinition] = []
        if not directory.is_dir():
            return definitions

        for prompt_file in sorted(directory.rglob("*.prompt.md")):
            metadata, body = _parse_markdown_asset(prompt_file.read_text(encoding="utf-8"))
            relative = prompt_file.relative_to(directory)
            name = str(
                metadata.get("name")
                or _name_from_relative_path(relative, suffixes=(".prompt.md", ".md"))
            )
            description = str(metadata.get("description") or "").strip()
            definitions.append(
                SkillDefinition(
                    name=name,
                    description=description,
                    instructions=body,
                    source_path=prompt_file,
                    source_kind="copilot_prompt",
                )
            )
        return definitions

    def _discover_gemini_commands(self, directory: Path) -> list[SkillDefinition]:
        """Load Gemini TOML commands as reusable skills."""

        definitions: list[SkillDefinition] = []
        if not directory.is_dir():
            return definitions

        for command_file in sorted(directory.rglob("*.toml")):
            raw_payload = tomllib.loads(command_file.read_text(encoding="utf-8"))
            if not isinstance(raw_payload, dict):
                continue

            relative = command_file.relative_to(directory)
            name = str(raw_payload.get("name") or _name_from_relative_path(relative, suffixes=(".toml",)))
            description = str(raw_payload.get("description") or "").strip()
            instructions = str(raw_payload.get("prompt") or "").strip()
            definitions.append(
                SkillDefinition(
                    name=name,
                    description=description,
                    instructions=instructions,
                    source_path=command_file,
                    source_kind="gemini_command",
                )
            )
        return definitions


def _render_native_skill_instructions(payload: dict[str, Any]) -> str:
    """Render a normalized instruction block from a native YAML skill file."""

    lines: list[str] = []
    steps = payload.get("steps")
    if isinstance(steps, list) and steps:
        lines.append("Steps:")
        for index, step in enumerate(steps, start=1):
            lines.append(f"{index}. {step}")

    parameters = payload.get("parameters")
    parameter_lines = _render_parameters(parameters)
    if parameter_lines:
        if lines:
            lines.append("")
        lines.extend(parameter_lines)

    if not lines:
        return str(payload.get("description") or "").strip()
    return "\n".join(lines).strip()


def _render_parameters(parameters: Any) -> list[str]:
    """Render parameter definitions from YAML-native skill metadata."""

    if not isinstance(parameters, list) or not parameters:
        return []

    rendered = ["Parameters:"]
    for parameter in parameters:
        if isinstance(parameter, str):
            rendered.append(f"- {parameter}")
            continue
        if isinstance(parameter, dict):
            for key, value in parameter.items():
                rendered.append(f"- {key}: {value}")
    return rendered


def _parse_markdown_asset(raw_text: str) -> tuple[dict[str, Any], str]:
    """Parse optional YAML frontmatter from a Markdown asset."""

    if not raw_text.startswith("---\n"):
        return {}, raw_text.strip()

    lines = raw_text.splitlines()
    try:
        end_index = lines[1:].index("---") + 1
    except ValueError:
        return {}, raw_text.strip()

    metadata_block = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()
    metadata = yaml.safe_load(metadata_block) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata, body


def _name_from_relative_path(relative_path: Path, *, suffixes: tuple[str, ...]) -> str:
    """Build a stable skill name from a path relative to its root directory."""

    path_str = relative_path.as_posix()
    for suffix in suffixes:
        if path_str.endswith(suffix):
            path_str = path_str[: -len(suffix)]
            break
    return path_str.replace("/", ":")
