"""Tests for the context command."""

from unittest.mock import Mock, patch

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.context import ContextCommand
from henchman.config.schema import ContextSettings, Settings
from henchman.core.agent import Agent
from henchman.core.session import Session


@pytest.fixture
def ctx():
    """Create a test command context."""
    console = Mock()
    console.print = Mock()

    session = Session(id="test", project_hash="abc", started="now", last_updated="now")

    agent = Mock(spec=Agent)
    agent.session = session

    tool_registry = Mock()

    return CommandContext(
        console=console,
        args=[],
        settings=None,
        agent=agent,
        tool_registry=tool_registry,
        session=session,
        repl=None,
        session_manager=None,
        project_hash="abc",
        mcp_manager=None,
    )


def test_context_command_properties():
    """Test ContextCommand basic properties."""
    cmd = ContextCommand()
    assert cmd.name == "context"
    assert cmd.description == "Manage intelligent context settings"
    assert cmd.usage == "/context [enable|disable|strategy|stats]"


@pytest.mark.asyncio
async def test_context_command_no_args(ctx):
    """Test context command with no arguments shows status."""
    cmd = ContextCommand()

    with patch("henchman.cli.commands.context.load_settings") as mock_load:
        mock_settings = Mock(spec=Settings)
        mock_settings.context = Mock(spec=ContextSettings)
        mock_settings.context.intelligent_context = False
        mock_settings.context.adaptive_compression = True
        mock_settings.context.max_tokens = 128000
        mock_settings.context.compaction_threshold = 0.75
        mock_settings.context.importance_threshold = 0.5
        mock_settings.context.cluster_similarity_threshold = 0.7
        mock_load.return_value = mock_settings

        await cmd.execute(ctx)

        # Should print status information
        assert ctx.console.print.called
        calls = ctx.console.print.call_args_list
        assert any("Intelligent Context Management" in str(call) for call in calls)


@pytest.mark.asyncio
async def test_context_command_enable(ctx):
    """Test enabling intelligent context."""
    cmd = ContextCommand()
    ctx.args = ["enable"]

    with (
        patch("henchman.cli.commands.context.load_settings") as mock_load,
        patch("henchman.cli.commands.context.save_settings") as mock_save,
    ):
        mock_settings = Mock(spec=Settings)
        mock_settings.context = Mock(spec=ContextSettings)
        mock_settings.context.intelligent_context = False
        mock_load.return_value = mock_settings

        await cmd.execute(ctx)

        # Should enable intelligent context and save settings
        assert mock_settings.context.intelligent_context is True
        mock_save.assert_called_once_with(mock_settings)
        assert ctx.console.print.called
        calls = ctx.console.print.call_args_list
        assert any("enabled" in str(call).lower() for call in calls)


@pytest.mark.asyncio
async def test_context_command_disable(ctx):
    """Test disabling intelligent context."""
    cmd = ContextCommand()
    ctx.args = ["disable"]

    with (
        patch("henchman.cli.commands.context.load_settings") as mock_load,
        patch("henchman.cli.commands.context.save_settings") as mock_save,
    ):
        mock_settings = Mock(spec=Settings)
        mock_settings.context = Mock(spec=ContextSettings)
        mock_settings.context.intelligent_context = True
        mock_load.return_value = mock_settings

        await cmd.execute(ctx)

        # Should disable intelligent context and save settings
        assert mock_settings.context.intelligent_context is False
        mock_save.assert_called_once_with(mock_settings)
        assert ctx.console.print.called
        calls = ctx.console.print.call_args_list
        assert any("disabled" in str(call).lower() for call in calls)


@pytest.mark.asyncio
async def test_context_command_strategy_no_args(ctx):
    """Test strategy subcommand with no arguments."""
    cmd = ContextCommand()
    ctx.args = ["strategy"]

    with patch("henchman.cli.commands.context.load_settings") as mock_load:
        mock_settings = Mock(spec=Settings)
        mock_settings.context = Mock(spec=ContextSettings)
        mock_settings.context.max_tokens = 128000
        mock_settings.context.compaction_threshold = 0.75
        mock_settings.context.importance_threshold = 0.5
        mock_settings.context.cluster_similarity_threshold = 0.7
        mock_settings.context.adaptive_compression = True
        mock_load.return_value = mock_settings

        await cmd.execute(ctx)

        # Should show strategy status
        assert ctx.console.print.called
        calls = ctx.console.print.call_args_list
        assert any("Compression Strategy Settings" in str(call) for call in calls)


@pytest.mark.asyncio
async def test_context_command_stats(ctx):
    """Test stats subcommand."""
    cmd = ContextCommand()
    ctx.args = ["stats"]

    # Mock the intelligent context manager
    mock_compactor = Mock()
    mock_compactor.get_statistics.return_value = {
        "total_messages": 10,
        "clusters_created": 2,
        "compression_ratio": 0.5,
        "tokens_saved": 1000,
    }
    ctx.agent.compactor = mock_compactor

    # Patch IntelligentContextManager so isinstance(mock_compactor, ...) returns True
    fake_class = type("IntelligentContextManager", (), {})
    mock_compactor.__class__ = fake_class
    with patch("henchman.utils.intelligent_context.IntelligentContextManager", fake_class):

        await cmd.execute(ctx)

        # Should show statistics
        assert ctx.console.print.called
        calls = ctx.console.print.call_args_list
        assert any("Context Usage Statistics" in str(call) for call in calls)


@pytest.mark.asyncio
async def test_context_command_invalid_subcommand(ctx):
    """Test context command with invalid subcommand."""
    cmd = ContextCommand()
    ctx.args = ["invalid"]

    await cmd.execute(ctx)

    # Should show usage help
    assert ctx.console.print.called
    calls = ctx.console.print.call_args_list
    assert any("Usage:" in str(call) for call in calls)
    assert any("Subcommands:" in str(call) for call in calls)


def test_context_command_registered():
    """Test that ContextCommand is properly registered in builtins."""
    from henchman.cli.commands.builtins import get_builtin_commands

    commands = get_builtin_commands()
    context_commands = [cmd for cmd in commands if cmd.name == "context"]
    assert len(context_commands) == 1
    assert isinstance(context_commands[0], ContextCommand)
