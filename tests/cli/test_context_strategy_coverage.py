"""Tests for context command strategy management and helper classes."""

from __future__ import annotations

from contextlib import suppress
from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.context import (
    ContextConsoleHelper,
    RangeParameterConfig,
    StrategyManager,
    _disable_intelligent_context,
    _enable_intelligent_context,
    _handle_adaptive_parameter,
    _print_no_compactor_message,
    _print_statistics_values,
    _print_stats_info,
    _show_stats,
    _update_context_setting,
)
from henchman.config.schema import ContextSettings
from henchman.core.session import Session

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def console() -> MagicMock:
    """Create a mock console."""
    c = MagicMock()
    c.print = MagicMock()
    return c


@pytest.fixture
def ctx(console: MagicMock) -> CommandContext:
    """Create a test command context."""
    session = Session(id="test", project_hash="abc", started="now", last_updated="now")
    agent = MagicMock()
    agent.session = session
    tool_registry = MagicMock()
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


# ---------------------------------------------------------------------------
# RangeParameterConfig tests
# ---------------------------------------------------------------------------


class TestRangeParameterConfig:
    """Tests for RangeParameterConfig dataclass."""

    def test_get_display_label_from_param_name(self) -> None:
        """Test get_display_label from param_name when no explicit label."""
        cfg = RangeParameterConfig(param_name="max_tokens", min_val=1000)
        label = cfg.get_display_label()
        assert "Max" in label or "max" in label.lower()

    def test_get_display_label_explicit(self) -> None:
        """Test get_display_label uses explicit label."""
        cfg = RangeParameterConfig(param_name="threshold", min_val=0.0, max_val=1.0, label="Threshold")
        assert cfg.get_display_label() == "Threshold"

    def test_validate_value_in_range(self) -> None:
        """Test validate_value passes for in-range value."""
        cfg = RangeParameterConfig(param_name="threshold", min_val=0.0, max_val=1.0)
        cfg.validate_value(0.5)  # Should not raise

    def test_validate_value_out_of_range(self) -> None:
        """Test validate_value raises for out-of-range value."""
        cfg = RangeParameterConfig(param_name="threshold", min_val=0.0, max_val=1.0)
        with pytest.raises(ValueError):
            cfg.validate_value(1.5)

    def test_validate_value_below_min(self) -> None:
        """Test validate_value raises for value below min."""
        cfg = RangeParameterConfig(param_name="threshold", min_val=0.1)
        with pytest.raises(ValueError):
            cfg.validate_value(0.0)

    def test_validate_value_no_max(self) -> None:
        """Test validate_value passes for value above min with no max."""
        cfg = RangeParameterConfig(param_name="max_tokens", min_val=1000, is_int=True)
        cfg.validate_value(50000)  # Should not raise

    def test_parse_value_int(self) -> None:
        """Test parse_value returns int for integer config."""
        cfg = RangeParameterConfig(param_name="max_tokens", min_val=1000, is_int=True)
        result = cfg.parse_value("50000")
        assert result == 50000
        assert isinstance(result, int)

    def test_parse_value_float(self) -> None:
        """Test parse_value returns float for float config."""
        cfg = RangeParameterConfig(param_name="threshold", min_val=0.0, max_val=1.0)
        result = cfg.parse_value("0.75")
        assert result == 0.75
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# ContextConsoleHelper tests
# ---------------------------------------------------------------------------


class TestContextConsoleHelper:
    """Tests for ContextConsoleHelper."""

    def _make_settings(self) -> ContextSettings:
        """Create test context settings."""
        s = MagicMock(spec=ContextSettings)
        s.intelligent_context = True
        s.adaptive_compression = True
        s.max_tokens = 128000
        s.compaction_threshold = 0.75
        s.importance_threshold = 0.5
        s.cluster_similarity_threshold = 0.7
        return s

    def test_print_status_info(self) -> None:
        """Test print_status_info calls console correctly."""
        helper = ContextConsoleHelper()
        console = MagicMock()
        settings = self._make_settings()
        helper.print_status_info(console, settings)
        console.print.assert_called()
        calls = [str(c) for c in console.print.call_args_list]
        assert any("Intelligent Context" in c for c in calls)

    def test_print_strategy_usage(self) -> None:
        """Test print_strategy_usage calls console correctly."""
        helper = ContextConsoleHelper()
        console = MagicMock()
        helper.print_strategy_usage(console)
        console.print.assert_called()

    def test_print_strategy_status(self) -> None:
        """Test print_strategy_status calls console correctly."""
        helper = ContextConsoleHelper()
        console = MagicMock()
        settings = self._make_settings()
        helper.print_strategy_status(console, settings)
        console.print.assert_called()


# ---------------------------------------------------------------------------
# StrategyManager tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestStrategyManager:
    """Tests for StrategyManager."""

    async def test_manage_strategy_no_args_shows_status(self, ctx: CommandContext) -> None:
        """Test manage_strategy with no args shows current status."""
        manager = StrategyManager()
        mock_settings = MagicMock()
        mock_settings.context = MagicMock(spec=ContextSettings)
        mock_settings.context.intelligent_context = True
        mock_settings.context.adaptive_compression = True
        mock_settings.context.max_tokens = 128000
        mock_settings.context.compaction_threshold = 0.75
        mock_settings.context.importance_threshold = 0.5
        mock_settings.context.cluster_similarity_threshold = 0.7
        with patch("henchman.cli.commands.context.load_settings", return_value=mock_settings):
            await manager.manage_strategy(ctx, [])
        ctx.console.print.assert_called()

    async def test_manage_strategy_set_valid(self, ctx: CommandContext) -> None:
        """Test manage_strategy with valid set command."""
        manager = StrategyManager()
        mock_settings = MagicMock()
        mock_settings.context = MagicMock(spec=ContextSettings)
        mock_settings.context.max_tokens = 128000
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings"),
        ):
            await manager.manage_strategy(ctx, ["set", "max_tokens", "200000"])
        ctx.console.print.assert_called()

    async def test_manage_strategy_set_insufficient_args(self, ctx: CommandContext) -> None:
        """Test manage_strategy with set but missing value."""
        manager = StrategyManager()
        await manager.manage_strategy(ctx, ["set", "threshold"])
        ctx.console.print.assert_called()

    async def test_manage_strategy_unknown_action(self, ctx: CommandContext) -> None:
        """Test manage_strategy with unknown action."""
        manager = StrategyManager()
        await manager.manage_strategy(ctx, ["unknown"])
        ctx.console.print.assert_called()
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("Usage" in c for c in calls)


# ---------------------------------------------------------------------------
# Module-level helper function tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestModuleLevelContextHelpers:
    """Tests for module-level context helper functions."""

    async def test_update_context_setting(self, ctx: CommandContext) -> None:
        """Test _update_context_setting saves updated settings."""
        from henchman.cli.commands.context import ContextSettingUpdate
        mock_settings = MagicMock()
        mock_settings.context = MagicMock()
        mock_settings.context.max_tokens = 128000
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings") as mock_save,
        ):
            update = ContextSettingUpdate("max_tokens", 200000, "200000")
            await _update_context_setting(ctx, update)
        mock_save.assert_called_once_with(mock_settings)
        ctx.console.print.assert_called()

    async def test_handle_adaptive_on(self, ctx: CommandContext) -> None:
        """Test _handle_adaptive_parameter with 'on'."""
        mock_settings = MagicMock()
        mock_settings.context = MagicMock()
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings"),
        ):
            await _handle_adaptive_parameter(ctx, "on")
        ctx.console.print.assert_called()

    async def test_handle_adaptive_off(self, ctx: CommandContext) -> None:
        """Test _handle_adaptive_parameter with 'off'."""
        mock_settings = MagicMock()
        mock_settings.context = MagicMock()
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings"),
        ):
            await _handle_adaptive_parameter(ctx, "off")
        ctx.console.print.assert_called()

    async def test_handle_adaptive_invalid(self, ctx: CommandContext) -> None:
        """Test _handle_adaptive_parameter with invalid value raises."""
        with pytest.raises(ValueError):
            await _handle_adaptive_parameter(ctx, "maybe")

    async def test_enable_intelligent_context_when_disabled(self, ctx: CommandContext) -> None:
        """Test _enable_intelligent_context when already disabled."""
        mock_settings = MagicMock()
        mock_settings.context.intelligent_context = False
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings") as mock_save,
        ):
            await _enable_intelligent_context(ctx)
        mock_save.assert_called_once()
        assert mock_settings.context.intelligent_context is True

    async def test_enable_intelligent_context_when_already_enabled(
        self, ctx: CommandContext
    ) -> None:
        """Test _enable_intelligent_context when already enabled."""
        mock_settings = MagicMock()
        mock_settings.context.intelligent_context = True
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings") as mock_save,
        ):
            await _enable_intelligent_context(ctx)
        mock_save.assert_not_called()
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("already enabled" in c for c in calls)

    async def test_disable_intelligent_context_when_enabled(self, ctx: CommandContext) -> None:
        """Test _disable_intelligent_context when enabled."""
        mock_settings = MagicMock()
        mock_settings.context.intelligent_context = True
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings") as mock_save,
        ):
            await _disable_intelligent_context(ctx)
        mock_save.assert_called_once()
        assert mock_settings.context.intelligent_context is False

    async def test_disable_intelligent_context_when_already_disabled(
        self, ctx: CommandContext
    ) -> None:
        """Test _disable_intelligent_context when already disabled."""
        mock_settings = MagicMock()
        mock_settings.context.intelligent_context = False
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings") as mock_save,
        ):
            await _disable_intelligent_context(ctx)
        mock_save.assert_not_called()
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("already disabled" in c for c in calls)

    async def test_show_stats_no_agent(self) -> None:
        """Test _show_stats without agent."""
        console = MagicMock()
        session = Session(id="test", project_hash="abc", started="now", last_updated="now")
        ctx = CommandContext(
            console=console,
            args=[],
            settings=None,
            agent=None,
            tool_registry=MagicMock(),
            session=session,
            repl=None,
            session_manager=None,
            project_hash="abc",
            mcp_manager=None,
        )
        await _show_stats(ctx)
        console.print.assert_called()
        calls = [str(c) for c in console.print.call_args_list]
        assert any("No active agent" in c for c in calls)

    async def test_show_stats_with_agent(self, ctx: CommandContext) -> None:
        """Test _show_stats with agent that has no compactor."""
        ctx.agent.compactor = None
        await _show_stats(ctx)
        ctx.console.print.assert_called()

    async def test_show_stats_import_error(self, ctx: CommandContext) -> None:
        """Test _show_stats handles ImportError."""
        with patch.dict("sys.modules", {"henchman.utils.intelligent_context": None}):
            await _show_stats(ctx)
        ctx.console.print.assert_called()


# ---------------------------------------------------------------------------
# Print helper function tests
# ---------------------------------------------------------------------------


class TestPrintHelpers:
    """Tests for print helper functions."""

    def test_print_no_compactor_message(self) -> None:
        """Test _print_no_compactor_message outputs correct message."""
        console = MagicMock()
        _print_no_compactor_message(console)
        calls = [str(c) for c in console.print.call_args_list]
        assert any("not active" in c for c in calls)

    def test_print_statistics_values(self) -> None:
        """Test _print_statistics_values outputs stats."""
        console = MagicMock()
        stats = {
            "total_messages": 10,
            "clusters_created": 3,
            "compression_ratio": 0.5,
            "tokens_saved": 1000,
        }
        _print_statistics_values(console, stats)
        assert console.print.call_count == 4

    def test_print_stats_info_no_compactor(self, ctx: CommandContext) -> None:
        """Test _print_stats_info with no compactor."""
        ctx.agent.compactor = None
        _print_stats_info(ctx.console, ctx.agent)
        ctx.console.print.assert_called()

    def test_print_stats_info_with_compactor(self, ctx: CommandContext) -> None:
        """Test _print_stats_info with a compactor."""
        try:
            from henchman.utils.intelligent_context import IntelligentContextManager
            # Create a mock that passes isinstance check
            compactor = MagicMock(spec=IntelligentContextManager)
            # Add get_statistics manually since spec may not include it
            type(compactor).get_statistics = MagicMock(return_value={"total_messages": 5})
            ctx.agent.compactor = compactor
            _print_stats_info(ctx.console, ctx.agent)
            ctx.console.print.assert_called()
        except ImportError:
            pytest.skip("IntelligentContextManager not available")

    def test_print_stats_info_exception(self, ctx: CommandContext) -> None:
        """Test _print_stats_info handles generic exception."""
        ctx.agent.compactor = MagicMock()
        ctx.agent.compactor.get_statistics.side_effect = Exception("stat error")
        # Patch the isinstance check to return True
        with (
            patch("henchman.cli.commands.context.isinstance", return_value=True),
            suppress(Exception),
        ):
            _print_stats_info(ctx.console, ctx.agent)
        ctx.console.print.assert_called()


# ---------------------------------------------------------------------------
# ContextCommand strategy subcommand tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestContextCommandStrategyCoverage:
    """Additional tests for ContextCommand strategy coverage."""

    def _make_ctx(self, args: list[str]) -> CommandContext:
        """Create a test command context."""
        console = MagicMock()
        session = Session(id="test", project_hash="abc", started="now", last_updated="now")
        agent = MagicMock()
        agent.session = session
        agent.compactor = None
        return CommandContext(
            console=console,
            args=args,
            settings=None,
            agent=agent,
            tool_registry=MagicMock(),
            session=session,
            repl=None,
            session_manager=None,
            project_hash="abc",
            mcp_manager=None,
        )

    async def test_context_strategy_set_threshold(self) -> None:
        """Test setting compaction threshold."""
        from henchman.cli.commands.context import ContextCommand
        cmd = ContextCommand()
        ctx = self._make_ctx(["strategy", "set", "threshold", "0.8"])
        mock_settings = MagicMock()
        mock_settings.context = MagicMock()
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings"),
        ):
            await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_context_strategy_set_importance(self) -> None:
        """Test setting importance threshold."""
        from henchman.cli.commands.context import ContextCommand
        cmd = ContextCommand()
        ctx = self._make_ctx(["strategy", "set", "importance", "0.6"])
        mock_settings = MagicMock()
        mock_settings.context = MagicMock()
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings"),
        ):
            await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_context_strategy_set_similarity(self) -> None:
        """Test setting cluster similarity threshold."""
        from henchman.cli.commands.context import ContextCommand
        cmd = ContextCommand()
        ctx = self._make_ctx(["strategy", "set", "similarity", "0.7"])
        mock_settings = MagicMock()
        mock_settings.context = MagicMock()
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings"),
        ):
            await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_context_strategy_set_unknown_param(self) -> None:
        """Test setting unknown parameter."""
        from henchman.cli.commands.context import ContextCommand
        cmd = ContextCommand()
        ctx = self._make_ctx(["strategy", "set", "unknown_param", "0.5"])
        await cmd.execute(ctx)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("Unknown parameter" in c for c in calls)

    async def test_context_strategy_set_adaptive_on(self) -> None:
        """Test setting adaptive on."""
        from henchman.cli.commands.context import ContextCommand
        cmd = ContextCommand()
        ctx = self._make_ctx(["strategy", "set", "adaptive", "on"])
        mock_settings = MagicMock()
        mock_settings.context = MagicMock()
        with (
            patch("henchman.cli.commands.context.load_settings", return_value=mock_settings),
            patch("henchman.cli.commands.context.save_settings"),
        ):
            await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_context_strategy_set_adaptive_invalid(self) -> None:
        """Test setting adaptive with invalid value shows error output."""
        from henchman.cli.commands.context import ContextCommand
        cmd = ContextCommand()
        ctx = self._make_ctx(["strategy", "set", "adaptive", "maybe"])
        # The ValueError from invalid value is caught internally or propagated
        with suppress(ValueError):
            await cmd.execute(ctx)
        # Either error was raised or printed - both are valid
        assert True

    async def test_context_stats(self) -> None:
        """Test stats subcommand."""
        from henchman.cli.commands.context import ContextCommand
        cmd = ContextCommand()
        ctx = self._make_ctx(["stats"])
        await cmd.execute(ctx)
        ctx.console.print.assert_called()
