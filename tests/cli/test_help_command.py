"""Tests for the enhanced Tier 1 help command."""

from __future__ import annotations

import click
from click.testing import CliRunner

from henchman.cli.commands.help_command import create_help_command
from henchman.tools.base import Tool, ToolResult
from henchman.tools.registry import ToolRegistry


class StaticTool(Tool):
    """Tool test double with stable metadata."""

    def __init__(self, tool_name: str, description: str) -> None:
        self._tool_name = tool_name
        self._description = description

    @property
    def name(self) -> str:
        return self._tool_name

    @property
    def description(self) -> str:
        return self._description

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content=str(params))


def _build_help_group() -> click.Group:
    """Build a click group with Tier 1-style commands and tools."""

    @click.group(name="henchman")
    def group() -> None:
        """Test root command."""

    @click.group(name="config", help="View and edit configuration values.")
    def config_command() -> None:
        """Config test command group."""

    @click.command(name="set", help="Persist one config key to an explicit scope.")
    def config_set_command() -> None:
        """Config set test command."""

    @click.command(name="unset", help="Remove one config key from an explicit scope.")
    def config_unset_command() -> None:
        """Config unset test command."""

    @click.command(name="export", help="Export one scope to a local config sync file.")
    def config_export_command() -> None:
        """Config export test command."""

    @click.command(name="list", help="List config keys for a selected scope.")
    def config_list_command() -> None:
        """Config list test command."""

    @click.command(name="upgrade", help="Upgrade the installed Henchman CLI safely.")
    def upgrade_command() -> None:
        """Upgrade test command."""

    tool_registry = ToolRegistry()
    tool_registry.register(StaticTool("mcp", "Inspect configured MCP servers."))
    tool_registry.register(StaticTool("mcp_auth", "Persist MCP auth tokens."))
    tool_registry.register(StaticTool("schedule_cron", "Persist cron schedule metadata."))
    tool_registry.register(StaticTool("skill", "Inspect bundled local skills."))
    tool_registry.register(StaticTool("shell", "Execute shell commands."))
    for name in ("task_get", "task_list", "task_output", "task_stop"):
        tool_registry.register(StaticTool(name, "Track background tasks."))
    tool_registry.register(StaticTool("web_search", "Search the web for current information."))

    config_command.add_command(config_set_command)
    config_command.add_command(config_unset_command)
    config_command.add_command(config_export_command)
    config_command.add_command(config_list_command)
    group.add_command(config_command)
    group.add_command(upgrade_command)
    group.add_command(create_help_command(tool_registry=tool_registry))
    return group


def test_help_lists_registered_commands_and_tools() -> None:
    """The help command should list the live command and tool surfaces."""
    runner = CliRunner()

    result = runner.invoke(_build_help_group(), ["help"])

    assert result.exit_code == 0
    assert "Commands:" in result.output
    assert "- config: View and edit configuration values." in result.output
    assert "- config export: Export one scope to a local config sync file." in result.output
    assert "- config list: List config keys for a selected scope." in result.output
    assert "- config set: Persist one config key to an explicit scope." in result.output
    assert "- config unset: Remove one config key from an explicit scope." in result.output
    assert "- upgrade: Upgrade the installed Henchman CLI safely." in result.output
    assert "Tools:" in result.output
    assert "- mcp: [runtime-wired] Inspect configured MCP servers." in result.output
    assert "- mcp_auth: [runtime-wired] Persist MCP auth tokens." in result.output
    assert "- schedule_cron: [metadata-only] Persist cron schedule metadata." in result.output
    assert "- skill: [local-only] Inspect bundled local skills." in result.output
    assert "- shell: [runtime-wired] Execute shell commands." in result.output
    assert "- web_search: [runtime-wired] Search the web for current information." in result.output
    assert "Capability truth:" in result.output
    assert "- plugin marketplace install: [unavailable]" in result.output
    assert "- GitHub webhook-helper: [docs-only]" in result.output
    assert "- Tier 10 dialogs: [undiscoverable]" in result.output


def test_help_filters_results_using_shared_metadata() -> None:
    """The search view should filter results by command/tool metadata."""
    runner = CliRunner()

    result = runner.invoke(_build_help_group(), ["help", "configuration"])

    assert result.exit_code == 0
    assert 'Search results for "configuration"' in result.output
    assert "- config: View and edit configuration values." in result.output
    assert "- config set:" not in result.output
    assert "- upgrade:" not in result.output
    assert "- shell:" not in result.output


def test_help_finds_nested_subcommands_by_full_name() -> None:
    """The search view should index nested click subcommands by their full path."""
    runner = CliRunner()

    result = runner.invoke(_build_help_group(), ["help", "config", "set"])

    assert result.exit_code == 0
    assert 'Search results for "config set"' in result.output
    assert "- config set: Persist one config key to an explicit scope." in result.output
    assert "- config unset:" not in result.output
    assert "- config export:" not in result.output
    assert "- config list:" not in result.output


def test_help_finds_nested_subcommands_by_leaf_name() -> None:
    """Leaf-name searches should still discover nested subcommands."""
    runner = CliRunner()

    result = runner.invoke(_build_help_group(), ["help", "unset"])

    assert result.exit_code == 0
    assert 'Search results for "unset"' in result.output
    assert "- config unset: Remove one config key from an explicit scope." in result.output
    assert "- config set:" not in result.output


def test_help_returns_actionable_guidance_for_unknown_queries() -> None:
    """Unknown searches should guide the user without failing the command."""
    runner = CliRunner()

    result = runner.invoke(_build_help_group(), ["help", "deploy"])

    assert result.exit_code == 0
    assert 'No help entries matched "deploy".' in result.output
    assert "Try `henchman help` to list every available command and tool." in result.output
    assert "Use `henchman <command> --help` for command-specific Click usage." in result.output


def test_help_searches_capability_truth_entries() -> None:
    """Capability-only surfaces should remain discoverable through help search."""
    runner = CliRunner()

    result = runner.invoke(_build_help_group(), ["help", "webhook"])

    assert result.exit_code == 0
    assert 'Search results for "webhook"' in result.output
    assert "- GitHub webhook-helper: [docs-only]" in result.output
    assert "- config:" not in result.output


def test_help_discovers_root_commands_through_lazy_wrapper() -> None:
    """Lazy wrapper execution should still search the real root command tree."""
    runner = CliRunner()
    root_group = _build_help_group()

    @click.group()
    def wrapper() -> None:
        """Wrapper group that simulates lazy root CLI dispatch."""

    @wrapper.command(
        name="help",
        add_help_option=False,
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    )
    @click.pass_context
    def lazy_help(ctx: click.Context) -> None:
        create_help_command(root_command=root_group).main(
            args=list(ctx.args),
            prog_name=ctx.command_path,
            standalone_mode=False,
        )

    result = runner.invoke(wrapper, ["help", "config"])

    assert result.exit_code == 0
    assert 'Search results for "config"' in result.output
    assert "- config: View and edit configuration values." in result.output
    assert "- config set:" in result.output
