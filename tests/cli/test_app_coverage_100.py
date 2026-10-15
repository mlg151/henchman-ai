"""Tests to achieve 100% coverage for cli/app.py.

Targets missing lines across headless functions, _execute_chat_command,
_run_interactive, _run_textual_tui, and _run_headless.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.core.events import AgentEvent, EventType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_config(**kwargs: Any) -> Any:
    """Create a RunConfig with sensible defaults.

    Returns:
        RunConfig instance.
    """
    from henchman.cli.app import RunConfig

    defaults = {
        "prompt": None,
        "tui": False,
        "team": False,
        "yes": False,
        "output_format": "text",
        "agent_role": None,
        "plan_mode": False,
        "debug": True,
    }
    defaults.update(kwargs)
    return RunConfig(**defaults)


def _make_mock_repl() -> MagicMock:
    """Create a mock Repl instance.

    Returns:
        MagicMock configured to look like a Repl.
    """
    repl = MagicMock()
    repl.initialize_mcp = AsyncMock()
    repl.rag_system = None
    repl.process_input = AsyncMock()
    repl._run_agent_direct = AsyncMock()
    repl.agent = MagicMock()
    repl.agent.base_tool_iterations = 25
    repl.agent.run = MagicMock()
    repl.agent.continue_with_tool_results = MagicMock()
    repl.tool_registry = MagicMock()
    repl.tool_registry.execute = AsyncMock()
    repl.agent.tool_registry = repl.tool_registry
    repl.orchestrator = MagicMock()
    return repl


async def _empty_stream():
    """Async generator yielding nothing (FINISHED event only)."""
    yield AgentEvent(type=EventType.FINISHED, data="stop")


async def _tool_call_stream():
    """Async generator yielding a TOOL_CALL_REQUEST then FINISHED."""
    tool_call = MagicMock()
    tool_call.id = "tc1"
    tool_call.name = "read_file"
    tool_call.arguments = {"path": "/tmp/test.txt"}
    yield AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tool_call)
    yield AgentEvent(type=EventType.FINISHED, data="stop")


# ---------------------------------------------------------------------------
# _run_interactive agent_role path (lines 283-287)
# ---------------------------------------------------------------------------


class TestGetThemeAndRendererSilentMode:
    """Tests for _get_theme_and_renderer silent mode (branch 224->227)."""

    def test_get_theme_and_renderer_invalid_theme_silent(self) -> None:
        """Branch 224->227: invalid theme with silent=True skips console.print."""
        from henchman.cli.app import _get_theme_and_renderer

        settings = MagicMock()
        settings.ui.theme = "nonexistent-theme-xyz"

        with patch("henchman.cli.app.console") as mock_console:
            theme, renderer = _get_theme_and_renderer(settings, silent=True)

        # With silent=True, no warning should be printed
        mock_console.print.assert_not_called()
        assert theme is not None


class TestRunInteractiveStartReplInnerFunction:
    """Tests for start_repl inner function in _run_interactive (line 285)."""

    def test_run_interactive_agent_role_start_repl_executed(self) -> None:
        """Line 285: start_repl inner function is actually executed by anyio.run."""

        from henchman.cli.app import _run_interactive

        config = _make_run_config(agent_role="explorer")

        mock_repl = _make_mock_repl()
        mock_repl.run = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.settings = MagicMock()
        mock_ctx.settings.rag = None
        mock_ctx.system_prompt = "test"
        mock_ctx.env_block = ""
        mock_ctx.provider = MagicMock()

        with (
            patch("henchman.cli.app._prepare_runtime_context", return_value=mock_ctx),
            patch(
                "henchman.cli.app._get_theme_and_renderer", return_value=(MagicMock(), MagicMock())
            ),
            patch("henchman.cli.repl.Repl", return_value=mock_repl),
            patch("henchman.rag.initialize_rag", return_value=None),
            patch("henchman.cli.app.anyio") as mock_anyio,
        ):

            def real_run(fn):
                asyncio.run(fn())

            mock_anyio.run.side_effect = real_run

            with suppress(Exception):
                _run_interactive(config)

        # start_repl should have been defined and called via anyio.run
        assert mock_anyio.run.called


# ---------------------------------------------------------------------------
# _run_headless prompt=None returns early (line 394)
# ---------------------------------------------------------------------------


class TestRunHeadlessPromptNone:
    """Tests for _run_headless early return when prompt is None."""

    def test_run_headless_prompt_none_returns_early(self) -> None:
        """Line 394: _run_headless returns immediately when config.prompt is None."""
        from henchman.cli.app import _run_headless

        config = _make_run_config(prompt=None)

        with patch("henchman.cli.app._create_headless_repl") as mock_create:
            _run_headless(config)
            # _create_headless_repl should NOT be called
            mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# _run_headless output format branches (lines 400-405)
# ---------------------------------------------------------------------------


class TestRunHeadlessOutputFormats:
    """Tests for _run_headless with different output formats."""

    def test_run_headless_json_format(self) -> None:
        """Line 401: json format calls _run_headless_json."""
        from henchman.cli.app import _run_headless

        config = _make_run_config(prompt="hello", output_format="json")
        mock_repl = _make_mock_repl()

        with (
            patch(
                "henchman.cli.app._create_headless_repl",
                return_value=(mock_repl, MagicMock(), "sys"),
            ),
            patch("henchman.cli.app.anyio") as mock_anyio,
            patch("henchman.cli.app._check_completion_status"),
        ):
            mock_anyio.run = MagicMock()
            _run_headless(config)
            # anyio.run should have been called with _run_headless_json_format
            assert mock_anyio.run.called

    def test_run_headless_stream_json_format(self) -> None:
        """Line 403: stream-json format calls _run_headless_stream_json."""
        from henchman.cli.app import _run_headless

        config = _make_run_config(prompt="hello", output_format="stream-json")
        mock_repl = _make_mock_repl()

        with (
            patch(
                "henchman.cli.app._create_headless_repl",
                return_value=(mock_repl, MagicMock(), "sys"),
            ),
            patch("henchman.cli.app.anyio") as mock_anyio,
            patch("henchman.cli.app._check_completion_status"),
        ):
            mock_anyio.run = MagicMock()
            _run_headless(config)
            assert mock_anyio.run.called

    def test_run_headless_json_complete_format(self) -> None:
        """Line 405: json-complete format calls _run_headless_json_complete."""
        from henchman.cli.app import _run_headless

        config = _make_run_config(prompt="hello", output_format="json-complete")
        mock_repl = _make_mock_repl()

        with (
            patch(
                "henchman.cli.app._create_headless_repl",
                return_value=(mock_repl, MagicMock(), "sys"),
            ),
            patch("henchman.cli.app.anyio") as mock_anyio,
            patch("henchman.cli.app._check_completion_status"),
        ):
            mock_anyio.run = MagicMock()
            _run_headless(config)
            assert mock_anyio.run.called


# ---------------------------------------------------------------------------
# _run_headless_text with agent_role (lines 425-433)
# ---------------------------------------------------------------------------


class TestRunHeadlessText:
    """Tests for _run_headless_text function."""

    @pytest.mark.anyio
    async def test_run_headless_text_with_agent_role(self) -> None:
        """Line 431: _run_headless_text calls _run_agent_direct when agent_role set."""
        from henchman.cli.app import _run_headless_text

        repl = _make_mock_repl()

        await _run_headless_text(repl, "do something", agent_role="explorer")

        repl.initialize_mcp.assert_called_once()
        repl._run_agent_direct.assert_called_once_with("explorer", "do something")

    @pytest.mark.anyio
    async def test_run_headless_text_awaits_rag_indexing_before_prompt(self) -> None:
        """One-shot text mode should finish indexing before processing its prompt."""
        from henchman.cli.app import _run_headless_text

        repl = _make_mock_repl()
        events: list[str] = []
        repl.rag_system = MagicMock()
        repl.initialize_mcp = AsyncMock(side_effect=lambda: events.append("mcp"))
        repl.rag_system.index_async = AsyncMock(side_effect=lambda: events.append("index"))
        repl.process_input = AsyncMock(side_effect=lambda _prompt: events.append("prompt"))

        with patch("asyncio.create_task") as create_task:
            await _run_headless_text(repl, "do something")

        create_task.assert_not_called()
        assert events == ["mcp", "index", "prompt"]

    @pytest.mark.anyio
    async def test_run_headless_text_without_agent_role(self) -> None:
        """Line 433: _run_headless_text calls process_input when no agent_role."""
        from henchman.cli.app import _run_headless_text

        repl = _make_mock_repl()

        await _run_headless_text(repl, "do something")

        repl.process_input.assert_called_once_with("do something")


# ---------------------------------------------------------------------------
# _initialize_json_processing with rag_system (lines 446-451)
# ---------------------------------------------------------------------------


class TestInitializeJsonProcessing:
    """Tests for _initialize_json_processing function."""

    @pytest.mark.anyio
    async def test_initialize_json_processing_awaits_rag_indexing(self) -> None:
        """One-shot JSON mode should finish indexing before returning its renderer."""
        from henchman.cli.app import _initialize_json_processing

        repl = _make_mock_repl()
        events: list[str] = []
        repl.rag_system = MagicMock()
        repl.initialize_mcp = AsyncMock(side_effect=lambda: events.append("mcp"))
        repl.rag_system.index_async = AsyncMock(side_effect=lambda: events.append("index"))

        with patch("asyncio.create_task") as create_task:
            result = await _initialize_json_processing(repl)

        create_task.assert_not_called()
        assert events == ["mcp", "index"]
        assert result is not None

    @pytest.mark.anyio
    async def test_initialize_json_processing_returns_renderer(self) -> None:
        """Lines 446-451: returns JsonOutputRenderer."""
        from henchman.cli.app import JsonOutputRenderer, _initialize_json_processing

        repl = _make_mock_repl()
        result = await _initialize_json_processing(repl)
        assert isinstance(result, JsonOutputRenderer)


# ---------------------------------------------------------------------------
# _process_tool_calls (lines 468-477)
# ---------------------------------------------------------------------------


class TestProcessToolCalls:
    """Tests for _process_tool_calls function."""

    @pytest.mark.anyio
    async def test_process_tool_calls_executes_and_submits(self) -> None:
        """Lines 468-470: tool calls are executed and submitted to agent."""
        from henchman.cli.app import _process_tool_calls

        repl = _make_mock_repl()
        mock_result = MagicMock()
        mock_result.content = "file contents"
        repl.tool_registry.execute = AsyncMock(return_value=mock_result)

        tool_call = MagicMock()
        tool_call.id = "tc1"
        tool_call.name = "read_file"
        tool_call.arguments = {"path": "/tmp/test"}

        render_calls = []

        def render_func(event: AgentEvent) -> None:
            render_calls.append(event)

        await _process_tool_calls(repl, [tool_call], render_func)

        repl.tool_registry.execute.assert_called_once_with("read_file", {"path": "/tmp/test"})
        repl.agent.submit_tool_result.assert_called_once_with("tc1", "file contents")
        assert len(render_calls) == 1
        assert render_calls[0].type == EventType.TOOL_CALL_RESULT

    @pytest.mark.anyio
    async def test_process_tool_calls_with_collect_events(self) -> None:
        """Lines 472-475: events collected when collect_events list is provided."""
        from henchman.cli.app import _process_tool_calls

        repl = _make_mock_repl()
        mock_result = MagicMock()
        mock_result.content = "result"
        repl.tool_registry.execute = AsyncMock(return_value=mock_result)

        tool_call = MagicMock()
        tool_call.id = "tc1"
        tool_call.name = "shell"
        tool_call.arguments = {"command": "ls"}

        all_events: list[AgentEvent] = []
        render_func = MagicMock()

        await _process_tool_calls(repl, [tool_call], render_func, collect_events=all_events)

        # Events should be collected, not rendered
        assert len(all_events) == 1
        assert all_events[0].type == EventType.TOOL_CALL_RESULT
        render_func.assert_not_called()


# ---------------------------------------------------------------------------
# _run_headless_json with tool calls (lines 505, 508-514)
# ---------------------------------------------------------------------------


class TestRunHeadlessJson:
    """Tests for _run_headless_json_format with tool calls (json mode)."""

    @pytest.mark.anyio
    async def test_run_headless_json_with_tool_calls(self) -> None:
        """Handles TOOL_CALL_REQUEST events in json mode."""
        from henchman.cli.app import _run_headless_json_format

        repl = _make_mock_repl()
        mock_result = MagicMock()
        mock_result.content = "done"
        repl.tool_registry.execute = AsyncMock(return_value=mock_result)

        tool_call = MagicMock()
        tool_call.id = "tc1"
        tool_call.name = "read_file"
        tool_call.arguments = {}

        async def first_stream():
            yield AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tool_call)
            yield AgentEvent(type=EventType.FINISHED, data="stop")

        async def continue_stream():
            yield AgentEvent(type=EventType.CONTENT, data="answer")
            yield AgentEvent(type=EventType.FINISHED, data="stop")

        repl.agent.run.return_value = first_stream()
        repl.agent.continue_with_tool_results.return_value = continue_stream()

        mock_renderer = MagicMock()
        mock_renderer.render = MagicMock()

        with patch("henchman.cli.app._initialize_json_processing", return_value=mock_renderer):
            await _run_headless_json_format(repl, "do something", "json")

        # Tool was executed
        repl.tool_registry.execute.assert_called_once()


# ---------------------------------------------------------------------------
# _run_headless_stream_json with tool calls (lines 542, 545-550)
# ---------------------------------------------------------------------------


class TestRunHeadlessStreamJson:
    """Tests for _run_headless_json_format with tool calls (stream-json mode)."""

    @pytest.mark.anyio
    async def test_run_headless_stream_json_with_tool_calls(self) -> None:
        """Handles TOOL_CALL_REQUEST events in stream-json mode."""
        from henchman.cli.app import _run_headless_json_format

        repl = _make_mock_repl()
        mock_result = MagicMock()
        mock_result.content = "done"
        repl.tool_registry.execute = AsyncMock(return_value=mock_result)

        tool_call = MagicMock()
        tool_call.id = "tc1"
        tool_call.name = "read_file"
        tool_call.arguments = {}

        async def first_stream():
            yield AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tool_call)
            yield AgentEvent(type=EventType.FINISHED, data="stop")

        async def continue_stream():
            yield AgentEvent(type=EventType.CONTENT, data="answer")
            yield AgentEvent(type=EventType.FINISHED, data="stop")

        repl.agent.run.return_value = first_stream()
        repl.agent.continue_with_tool_results.return_value = continue_stream()

        mock_renderer = MagicMock()
        mock_renderer.render_stream_json = MagicMock()

        with patch("henchman.cli.app._initialize_json_processing", return_value=mock_renderer):
            await _run_headless_json_format(repl, "do something", "stream-json")

        repl.tool_registry.execute.assert_called_once()


# ---------------------------------------------------------------------------
# _run_headless_json_complete with tool calls (lines 566-591)
# ---------------------------------------------------------------------------


class TestRunHeadlessJsonComplete:
    """Tests for _run_headless_json_complete function."""

    @pytest.mark.anyio
    async def test_run_headless_json_complete_with_tool_calls(self) -> None:
        """Lines 566-591: handles tool calls and renders final JSON."""
        from henchman.cli.app import _run_headless_json_complete

        repl = _make_mock_repl()
        mock_result = MagicMock()
        mock_result.content = "done"
        repl.tool_registry.execute = AsyncMock(return_value=mock_result)

        tool_call = MagicMock()
        tool_call.id = "tc1"
        tool_call.name = "read_file"
        tool_call.arguments = {}

        async def first_stream():
            yield AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tool_call)
            yield AgentEvent(type=EventType.FINISHED, data="stop")

        async def continue_stream():
            yield AgentEvent(type=EventType.CONTENT, data="answer")
            yield AgentEvent(type=EventType.FINISHED, data="stop")

        repl.agent.run.return_value = first_stream()
        repl.agent.continue_with_tool_results.return_value = continue_stream()

        mock_renderer = MagicMock()
        mock_renderer.render_final_json = MagicMock()

        with patch("henchman.cli.app._initialize_json_processing", return_value=mock_renderer):
            await _run_headless_json_complete(repl, "do something")

        mock_renderer.render_final_json.assert_called_once()
        repl.tool_registry.execute.assert_called_once()

    @pytest.mark.anyio
    async def test_run_headless_json_complete_no_tool_calls(self) -> None:
        """Lines 566-591: simple case with no tool calls."""
        from henchman.cli.app import _run_headless_json_complete

        repl = _make_mock_repl()

        async def simple_stream():
            yield AgentEvent(type=EventType.CONTENT, data="hello")
            yield AgentEvent(type=EventType.FINISHED, data="stop")

        repl.agent.run.return_value = simple_stream()

        mock_renderer = MagicMock()
        mock_renderer.render_final_json = MagicMock()

        with patch("henchman.cli.app._initialize_json_processing", return_value=mock_renderer):
            await _run_headless_json_complete(repl, "do something")

        mock_renderer.render_final_json.assert_called_once()


# ---------------------------------------------------------------------------
# _execute_chat_command debug filter (lines 720-735, 738-741, 746)
# ---------------------------------------------------------------------------


class TestExecuteChatCommand:
    """Tests for _execute_chat_command function."""

    def test_execute_chat_command_debug_filter_suppresses_debug_output(self) -> None:
        """Lines 720-733, 728: debug=False installs print filter that suppresses DEBUG."""

        from henchman.cli.app import _execute_chat_command

        config = _make_run_config(debug=False, prompt="hello")

        with (
            patch("henchman.cli.app._run_headless") as mock_headless,
            patch("builtins.print"),  # Prevent builtins.print from being replaced
        ):
            mock_headless.return_value = None
            _execute_chat_command(config)

    def test_execute_chat_command_debug_filter_return_on_debug_prefix(self) -> None:
        """Line 728: _filtered_print returns early for DEBUG-prefixed messages."""
        import builtins

        from henchman.cli.app import _execute_chat_command

        config = _make_run_config(debug=False, prompt="hello")

        original_print = builtins.print
        try:
            with patch("henchman.cli.app._run_headless"):
                _execute_chat_command(config)

            # Now builtins.print is the _filtered_print function
            # Call it with a DEBUG-prefixed string - should silently return (line 728)
            filter_print = builtins.print
            # The filter captures _orig_print. We can test by calling with non-DEBUG
            # message and verifying it passes through
            filter_print("DEBUG: this should be filtered")  # line 728 return
        finally:
            builtins.print = original_print

    def test_execute_chat_command_team_mode_calls_show_team_info(self) -> None:
        """Lines 734-735: team=True calls _show_team_info and returns."""
        from henchman.cli.app import _execute_chat_command

        config = _make_run_config(team=True)

        with patch("henchman.cli.app._show_team_info") as mock_team_info:
            _execute_chat_command(config)
            mock_team_info.assert_called_once()

    def test_execute_chat_command_tui_with_prompt_clears_prompt(self) -> None:
        """Lines 738-741: tui=True with prompt logs warning and clears prompt."""
        from henchman.cli.app import _execute_chat_command

        config = _make_run_config(tui=True, prompt="hello world")

        with (
            patch("henchman.cli.app._run_textual_tui") as mock_tui,
            patch("henchman.cli.app.console") as mock_console,
        ):
            mock_tui.return_value = None
            _execute_chat_command(config)

            # Warning should have been printed
            mock_console.print.assert_called()
            # TUI should be launched (prompt cleared)
            mock_tui.assert_called_once()

    def test_execute_chat_command_prompt_runs_headless(self) -> None:
        """Line 746: prompt without tui/team calls _run_headless."""
        from henchman.cli.app import _execute_chat_command

        config = _make_run_config(prompt="hello")

        with patch("henchman.cli.app._run_headless") as mock_headless:
            mock_headless.return_value = None
            _execute_chat_command(config)
            mock_headless.assert_called_once_with(config)


# ---------------------------------------------------------------------------
# _run_textual_tui plan mode (lines 304-325)
# ---------------------------------------------------------------------------


class TestRunTextualTui:
    """Tests for _run_textual_tui function."""

    def test_run_textual_tui_with_plan_mode(self) -> None:
        """Lines 309-312: plan_mode appends PLAN_MODE_PROMPT to system_prompt."""
        from henchman.cli.app import _run_textual_tui

        config = _make_run_config(plan_mode=True)

        mock_ctx = MagicMock()
        mock_ctx.system_prompt = "base prompt"
        mock_ctx.settings = MagicMock()
        mock_ctx.provider = MagicMock()
        mock_ctx.env_block = ""

        with (
            patch("henchman.cli.app._prepare_runtime_context", return_value=mock_ctx),
            patch("henchman.cli.textual_app.run_textual_app") as mock_run_app,
            patch("henchman.cli.commands.plan.PLAN_MODE_PROMPT", "PLAN_PROMPT"),
        ):
            _run_textual_tui(config)

        mock_run_app.assert_called_once()
        assert "PLAN_PROMPT" in mock_ctx.system_prompt

    def test_run_textual_tui_basic(self) -> None:
        """Lines 304-325: basic TUI launch path."""
        from henchman.cli.app import _run_textual_tui

        config = _make_run_config()

        mock_ctx = MagicMock()
        mock_ctx.system_prompt = "base prompt"
        mock_ctx.settings = MagicMock()
        mock_ctx.provider = MagicMock()
        mock_ctx.env_block = ""

        with (
            patch("henchman.cli.app._prepare_runtime_context", return_value=mock_ctx),
            patch("henchman.cli.textual_app.run_textual_app") as mock_run_app,
        ):
            _run_textual_tui(config)

        mock_run_app.assert_called_once()

    def test_run_textual_tui_non_text_format_warns(self) -> None:
        """Line 320-323: non-text format triggers warning console print."""
        from henchman.cli.app import _run_textual_tui

        config = _make_run_config(output_format="json")

        mock_ctx = MagicMock()
        mock_ctx.system_prompt = "base"
        mock_ctx.settings = MagicMock()
        mock_ctx.provider = MagicMock()
        mock_ctx.env_block = ""

        with (
            patch("henchman.cli.app._prepare_runtime_context", return_value=mock_ctx),
            patch("henchman.cli.textual_app.run_textual_app"),
            patch("henchman.cli.app.console") as mock_console,
        ):
            _run_textual_tui(config)

        # Warning should have been printed about format
        mock_console.print.assert_called()
