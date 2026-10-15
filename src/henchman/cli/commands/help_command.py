"""Enhanced help command for searchable Tier 1 command and tool discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass

import click

from henchman.cli.commands.discovery_capabilities import (
    build_discovery_capabilities,
    classify_registered_tool,
)
from henchman.tools.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class _HelpEntry:
    """Searchable help entry built from live command or tool metadata."""

    kind: str
    name: str
    summary: str
    usage: str | None = None
    detail: str | None = None

    @property
    def search_text(self) -> str:
        """Return normalized searchable text for the entry."""
        parts = [self.kind, self.name, self.summary]
        if self.detail:
            parts.append(self.detail)
        if self.usage:
            parts.append(self.usage)
        return " ".join(parts).casefold()

    @property
    def search_tokens(self) -> tuple[str, ...]:
        """Return normalized search tokens for precise matching."""
        return _tokenize_search_text(self.search_text)


def create_help_command(
    *,
    tool_registry: ToolRegistry | None = None,
    root_command: click.Group | None = None,
) -> click.Command:
    """Create the explicit searchable help command.

    Args:
        tool_registry: Optional live tool registry to surface registered tools.
        root_command: Optional explicit root click group used for command discovery.

    Returns:
        A click command that lists and searches commands and tools.
    """

    @click.command(name="help", help="Search commands and tools with shared metadata.")
    @click.argument("query_parts", nargs=-1)
    @click.pass_context
    def help_command(ctx: click.Context, query_parts: tuple[str, ...]) -> None:
        resolved_root_command = root_command or ctx.find_root().command
        query = " ".join(query_parts).strip()
        command_entries = _collect_command_entries(resolved_root_command)
        tool_entries = _collect_tool_entries(tool_registry)
        capability_entries = _collect_capability_entries(tool_registry)
        click.echo(
            _render_help_text(
                root_name=resolved_root_command.name or "henchman",
                query=query,
                command_entries=command_entries,
                tool_entries=tool_entries,
                capability_entries=capability_entries,
            )
        )

    return help_command


def register_help_command(
    cli: click.Group,
    *,
    tool_registry: ToolRegistry | None = None,
    root_command: click.Group | None = None,
) -> click.Command:
    """Register the searchable help command on a click group.

    Args:
        cli: Root click group that should expose the help command.
        tool_registry: Optional live tool registry to surface registered tools.
        root_command: Optional explicit root click group used for command discovery.

    Returns:
        The command instance added to ``cli``.
    """
    command = create_help_command(
        tool_registry=tool_registry,
        root_command=root_command or cli,
    )
    cli.add_command(command)
    return command


def _collect_command_entries(root_command: click.Command) -> tuple[_HelpEntry, ...]:
    """Collect searchable entries for visible click subcommands."""
    if not isinstance(root_command, click.Group):
        return ()

    root_context = click.Context(root_command, info_name=root_command.name or "henchman")
    return tuple(_collect_group_entries(group=root_command, parent_context=root_context, path_parts=()))


def _collect_group_entries(
    *,
    group: click.Group,
    parent_context: click.Context,
    path_parts: tuple[str, ...],
) -> list[_HelpEntry]:
    """Collect entries for one click group and its visible descendants."""
    entries: list[_HelpEntry] = []
    for command_name in group.list_commands(parent_context):
        command = group.get_command(parent_context, command_name)
        if command is None or command.hidden:
            continue
        command_context = click.Context(
            command,
            info_name=command_name,
            parent=parent_context,
        )
        full_path = (*path_parts, command_name)
        entries.append(
            _HelpEntry(
                kind="command",
                name=" ".join(full_path),
                summary=command.get_short_help_str() or "No summary available.",
                usage=_build_usage_hint(command_context=command_context),
            )
        )
        if isinstance(command, click.Group):
            entries.extend(
                _collect_group_entries(
                    group=command,
                    parent_context=command_context,
                    path_parts=full_path,
                )
            )
    return entries


def _build_usage_hint(
    *,
    command_context: click.Context,
) -> str:
    """Build a usage hint directly from click metadata."""
    usage = command_context.command.get_usage(command_context).strip()
    return usage.removeprefix("Usage: ").strip()


def _collect_tool_entries(tool_registry: ToolRegistry | None) -> tuple[_HelpEntry, ...]:
    """Collect searchable entries for live registered tools."""
    if tool_registry is None:
        return ()

    registered_tool_names = tuple(tool_registry.list_tools())
    declarations = sorted(tool_registry.get_declarations(), key=lambda declaration: declaration.name)
    return tuple(
        _HelpEntry(
            kind="tool",
            name=declaration.name,
            summary=_build_tool_summary(
                declaration.name,
                declaration.description or "No summary available.",
                registered_tool_names=registered_tool_names,
            ),
        )
        for declaration in declarations
    )


def _build_tool_summary(
    tool_name: str,
    description: str,
    *,
    registered_tool_names: tuple[str, ...],
) -> str:
    """Return a help summary for one tool with classification when available."""

    capability = classify_registered_tool(
        tool_name,
        registered_tool_names=registered_tool_names,
    )
    if capability is None:
        return description
    return f"[{capability.classification}] {description}"


def _collect_capability_entries(tool_registry: ToolRegistry | None) -> tuple[_HelpEntry, ...]:
    """Collect canonical runtime-truth capability classifications."""

    registered_tool_names = tuple(tool_registry.list_tools()) if tool_registry is not None else ()
    return tuple(
        _HelpEntry(
            kind="capability",
            name=capability.name,
            summary=f"[{capability.classification}] {capability.summary}",
            detail=capability.detail,
        )
        for capability in build_discovery_capabilities(
            registered_tool_names=registered_tool_names,
        )
    )


def _render_help_text(
    *,
    root_name: str,
    query: str,
    command_entries: tuple[_HelpEntry, ...],
    tool_entries: tuple[_HelpEntry, ...],
    capability_entries: tuple[_HelpEntry, ...],
) -> str:
    """Render deterministic help text for list and search modes."""
    matched_commands = _filter_entries(command_entries, query=query)
    matched_tools = _filter_entries(tool_entries, query=query)
    matched_capabilities = _filter_entries(capability_entries, query=query)

    if query and not matched_commands and not matched_tools and not matched_capabilities:
        return (
            f'No help entries matched "{query}".\n'
            f"Try `{root_name} help` to list every available command and tool.\n"
            f"Use `{root_name} <command> --help` for command-specific Click usage."
        )

    lines = ["Henchman enhanced help" if not query else f'Search results for "{query}"']
    if matched_commands:
        lines.extend(_render_command_section(matched_commands))
    if matched_tools:
        lines.extend(_render_tool_section(matched_tools))
    if matched_capabilities:
        lines.extend(_render_capability_section(matched_capabilities))
    if not matched_tools and not query:
        lines.extend(["Tools:", "- No tools are currently registered."])
    return "\n".join(lines)


def _filter_entries(entries: tuple[_HelpEntry, ...], *, query: str) -> tuple[_HelpEntry, ...]:
    """Filter entries using case-insensitive token matching."""
    if not query:
        return entries

    tokens = _tokenize_search_text(query)
    return tuple(
        entry
        for entry in entries
        if all(token in entry.search_tokens for token in tokens)
    )


def _tokenize_search_text(value: str) -> tuple[str, ...]:
    """Tokenize search text on non-alphanumeric boundaries."""
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def _render_command_section(entries: tuple[_HelpEntry, ...]) -> list[str]:
    """Render the command entries."""
    lines = ["Commands:"]
    for entry in entries:
        lines.append(f"- {entry.name}: {entry.summary}")
        if entry.usage:
            lines.append(f"  usage: {entry.usage}")
    return lines


def _render_tool_section(entries: tuple[_HelpEntry, ...]) -> list[str]:
    """Render the tool entries."""
    lines = ["Tools:"]
    for entry in entries:
        lines.append(f"- {entry.name}: {entry.summary}")
    return lines


def _render_capability_section(entries: tuple[_HelpEntry, ...]) -> list[str]:
    """Render the capability classification entries."""

    lines = ["Capability truth:"]
    for entry in entries:
        lines.append(f"- {entry.name}: {entry.summary}")
        if entry.detail:
            lines.append(f"  detail: {entry.detail}")
    return lines


__all__ = ["create_help_command", "register_help_command"]
