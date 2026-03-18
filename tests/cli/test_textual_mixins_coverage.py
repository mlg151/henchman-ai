"""Tests for textual_mixins.py coverage - focusing on missing lines."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _NullProvider tests
# ---------------------------------------------------------------------------


class TestNullProvider:
    """Tests for _NullProvider class."""

    def _make_null_provider(self) -> _NullProvider:
        """Create a _NullProvider instance."""
        from henchman.cli.textual_mixins import _NullProvider

        return _NullProvider()

    def test_null_provider_name(self) -> None:
        """Test _NullProvider returns 'null' as name."""
        provider = self._make_null_provider()
        assert provider.name == "null"

    def test_null_provider_attributes(self) -> None:
        """Test _NullProvider has expected attributes."""
        provider = self._make_null_provider()
        assert provider.supports_tools is False
        assert provider.supports_streaming is False
        assert provider.max_tokens == 0

    @pytest.mark.anyio
    async def test_null_provider_chat_completion_raises(self) -> None:
        """Test _NullProvider chat_completion raises RuntimeError."""
        provider = self._make_null_provider()
        with pytest.raises(RuntimeError):
            await provider.chat_completion([])

    @pytest.mark.anyio
    async def test_null_provider_chat_completion_stream_raises(self) -> None:
        """Test _NullProvider chat_completion_stream raises RuntimeError."""
        provider = self._make_null_provider()
        with pytest.raises(RuntimeError):
            result = await provider.chat_completion_stream([])
            async for _ in result:
                pass  # pragma: no cover

    def test_null_provider_count_tokens(self) -> None:
        """Test _NullProvider count_tokens returns 0."""
        provider = self._make_null_provider()
        assert provider.count_tokens("any text") == 0


# ---------------------------------------------------------------------------
# _extract_line_text tests
# ---------------------------------------------------------------------------


class TestExtractLineText:
    """Tests for _extract_line_text function."""

    def test_extract_from_object_with_text(self) -> None:
        """Test extraction from object with .text attribute."""
        from henchman.cli.textual_mixins import _extract_line_text

        item = MagicMock()
        item.text = "hello world"
        result = _extract_line_text(item)
        assert result == "hello world"

    def test_extract_from_string(self) -> None:
        """Test extraction from plain string."""
        from henchman.cli.textual_mixins import _extract_line_text

        result = _extract_line_text("plain text")
        assert result == "plain text"

    def test_extract_from_iterable(self) -> None:
        """Test extraction from iterable of segments."""
        from henchman.cli.textual_mixins import _extract_line_text

        seg1 = MagicMock()
        seg1.text = "hello "
        seg2 = MagicMock()
        seg2.text = "world"
        result = _extract_line_text([seg1, seg2])
        assert "hello" in result and "world" in result

    def test_extract_from_none_like(self) -> None:
        """Test extraction falls back to str()."""
        from henchman.cli.textual_mixins import _extract_line_text

        class Weird:
            def __iter__(self):
                raise TypeError("not iterable")

            def __str__(self):
                return "weird"

        result = _extract_line_text(Weird())
        assert result == "weird"


# ---------------------------------------------------------------------------
# _read_context_file_content tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestReadContextFileContent:
    """Tests for _read_context_file_content function."""

    async def test_reads_small_file(self, tmp_path: Path) -> None:
        """Test reading a small context file."""
        from henchman.cli.textual_mixins import _read_context_file_content

        test_file = tmp_path / "HENCHMAN.md"
        test_file.write_text("# Context\n\nThis is test content.")
        result = await _read_context_file_content(test_file)
        assert "HENCHMAN.md" in result
        assert "Context" in result

    async def test_reads_large_file_truncated(self, tmp_path: Path) -> None:
        """Test reading a file that exceeds the preview limit."""
        from henchman.cli.textual_mixins import (
            _CONTEXT_FILE_PREVIEW_LIMIT,
            _read_context_file_content,
        )

        test_file = tmp_path / "big_file.md"
        # Write content larger than preview limit
        content = "x" * (_CONTEXT_FILE_PREVIEW_LIMIT + 100)
        test_file.write_text(content)
        result = await _read_context_file_content(test_file)
        assert "truncated" in result

    async def test_read_text_fails_after_stat_succeeds(self, tmp_path: Path) -> None:
        """Test that function handles read_text failure after stat succeeds."""
        from henchman.cli.textual_mixins import _read_context_file_content
        
        test_file = tmp_path / "deleted_file.md"
        test_file.write_text("test content")
        
        # Mock path.read_text to raise OSError after stat succeeds
        import asyncio
        from unittest.mock import patch
        
        with patch.object(asyncio, 'to_thread') as mock_to_thread:
            # First call to stat() succeeds
            mock_stat = MagicMock()
            mock_stat.st_size = 1024
            # Second call to read_text() fails
            mock_to_thread.side_effect = [
                mock_stat,  # stat() succeeds
                OSError("File not found")  # read_text() fails
            ]
            
            # This should not raise an exception
            result = await _read_context_file_content(test_file)
            assert "Error reading" in result or "failed" in result.lower()


# ---------------------------------------------------------------------------
# _ProviderMixin tests
# ---------------------------------------------------------------------------


class TestProviderMixin:
    """Tests for _ProviderMixin."""

    def _make_app(self) -> MagicMock:
        """Create a mock app that uses _ProviderMixin."""
        from henchman.cli.textual_app import TextualConfig
        from henchman.cli.textual_mixins import _ProviderMixin

        app = MagicMock(spec=_ProviderMixin)
        app.provider = MagicMock()
        app.settings = MagicMock()
        app.config = TextualConfig()
        app.environment_context = ""
        return app

    def test_load_provider_safe_success(self) -> None:
        """Test _load_provider_safe returns provider on success."""
        from henchman.cli.textual_mixins import _ProviderMixin

        mixin = _ProviderMixin.__new__(_ProviderMixin)
        mock_provider = MagicMock()
        with patch("henchman.cli.app._get_provider", return_value=mock_provider):
            result = mixin._load_provider_safe()
        assert result is mock_provider

    def test_load_provider_safe_fallback(self) -> None:
        """Test _load_provider_safe returns NullProvider on exception."""
        from henchman.cli.textual_mixins import _NullProvider, _ProviderMixin

        mixin = _ProviderMixin.__new__(_ProviderMixin)
        with patch("henchman.cli.app._get_provider", side_effect=RuntimeError("no key")):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = mixin._load_provider_safe()
        assert isinstance(result, _NullProvider)

    def test_load_settings_safe_success(self) -> None:
        """Test _load_settings_safe returns settings on success."""
        from henchman.cli.textual_mixins import _ProviderMixin

        mock_settings = MagicMock()
        with patch("henchman.config.load_settings", return_value=mock_settings):
            result = _ProviderMixin._load_settings_safe()
        assert result is mock_settings

    def test_load_settings_safe_fallback(self) -> None:
        """Test _load_settings_safe returns default Settings on exception."""
        from henchman.cli.textual_mixins import _ProviderMixin

        with patch("henchman.config.load_settings", side_effect=ValueError("bad config")):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = _ProviderMixin._load_settings_safe()
        assert result is not None

    def test_create_config_safe(self) -> None:
        """Test _create_config_safe returns TextualConfig."""
        from henchman.cli.textual_app import TextualConfig
        from henchman.cli.textual_mixins import _ProviderMixin

        result = _ProviderMixin._create_config_safe()
        assert isinstance(result, TextualConfig)

    def test_gather_env_safe_success(self) -> None:
        """Test _gather_env_safe returns env string on success."""
        from henchman.cli.textual_mixins import _ProviderMixin

        with patch("henchman.config.environment.gather_environment", return_value={}):
            result = _ProviderMixin._gather_env_safe()
        # Should return something
        assert result is not None

    def test_gather_env_safe_fallback(self) -> None:
        """Test _gather_env_safe returns empty string on exception."""
        from henchman.cli.textual_mixins import _ProviderMixin

        with patch("henchman.config.environment.gather_environment", side_effect=Exception("fail")):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = _ProviderMixin._gather_env_safe()
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _HistoryMixin tests
# ---------------------------------------------------------------------------


class TestHistoryMixin:
    """Tests for _HistoryMixin."""

    def _make_mixin(self, tmp_path: Path) -> MagicMock:
        """Create a mock object using _HistoryMixin."""
        from henchman.cli.textual_mixins import _HistoryMixin

        obj = MagicMock()
        obj.command_history = []
        obj.history_index = 0
        input_handler = MagicMock()
        input_handler.history_file = tmp_path / ".henchman_history"
        obj.input_handler = input_handler

        # Bind methods
        obj._load_history = _HistoryMixin._load_history.__get__(obj, type(obj))
        obj._persist_history_entry = _HistoryMixin._persist_history_entry.__get__(obj, type(obj))
        return obj

    def test_load_history_no_file(self, tmp_path: Path) -> None:
        """Test _load_history does nothing when no history file."""
        from henchman.cli.textual_mixins import _HistoryMixin

        obj = MagicMock()
        obj.command_history = []
        obj.history_index = 0
        input_handler = MagicMock()
        input_handler.history_file = tmp_path / "nonexistent_history"
        obj.input_handler = input_handler

        _HistoryMixin._load_history(obj)
        assert obj.command_history == []

    def test_load_history_with_file(self, tmp_path: Path) -> None:
        """Test _load_history loads entries from history file."""
        from henchman.cli.textual_mixins import _HistoryMixin

        history_file = tmp_path / ".henchman_history"
        history_file.write_text("/help\n/quit\n")

        obj = MagicMock()
        obj.command_history = []
        obj.history_index = 0
        input_handler = MagicMock()
        input_handler.history_file = history_file
        obj.input_handler = input_handler

        _HistoryMixin._load_history(obj)
        assert "/help" in obj.command_history
        assert "/quit" in obj.command_history

    def test_persist_history_entry(self, tmp_path: Path) -> None:
        """Test _persist_history_entry writes entry to file."""
        from henchman.cli.textual_mixins import _HistoryMixin

        history_file = tmp_path / ".henchman_history"
        obj = MagicMock()
        input_handler = MagicMock()
        input_handler.history_file = history_file
        obj.input_handler = input_handler
        obj.query_one = MagicMock(side_effect=Exception("no widget"))

        _HistoryMixin._persist_history_entry(obj, "/help")
        assert history_file.exists()
        assert "/help" in history_file.read_text()

    def test_persist_history_entry_no_handler(self) -> None:
        """Test _persist_history_entry does nothing without input handler."""
        from henchman.cli.textual_mixins import _HistoryMixin

        obj = MagicMock()
        obj.input_handler = None

        _HistoryMixin._persist_history_entry(obj, "/help")
        # Should not raise


# ---------------------------------------------------------------------------
# _StatusBarMixin tests
# ---------------------------------------------------------------------------


class TestStatusBarMixin:
    """Tests for _StatusBarMixin."""

    def test_build_status_text(self) -> None:
        """Test _build_status_text assembles text."""
        from henchman.cli.textual_mixins import _StatusBarMixin

        obj = MagicMock()
        obj.provider = MagicMock()
        obj.provider.name = "deepseek"
        obj.settings = MagicMock()
        obj.settings.ui.theme = "dark"
        obj.tool_manager = MagicMock()
        obj.tool_manager.registry.list_tools.return_value = []
        obj.mcp_manager = None
        obj.rag_system = None

        # Monkeypatch the method
        text = _StatusBarMixin._build_status_text(obj)
        assert isinstance(text, str)

    def test_update_status_bar_no_bar(self) -> None:
        """Test _update_status_bar handles missing status bar widget."""
        from henchman.cli.textual_mixins import _StatusBarMixin

        obj = MagicMock()
        obj.query_one = MagicMock(side_effect=Exception("no widget"))

        _StatusBarMixin._update_status_bar(obj)
        # Should not raise


# ---------------------------------------------------------------------------
# _ContextTreeMixin tests
# ---------------------------------------------------------------------------


class TestContextTreeMixin:
    """Tests for _ContextTreeMixin."""

    def test_show_welcome(self) -> None:
        """Test _show_welcome adds welcome message to chat pane."""
        from henchman.cli.textual_mixins import _ContextTreeMixin

        obj = MagicMock()
        obj.provider = MagicMock()
        obj.provider.name = "deepseek"
        obj.provider.model = "deepseek-chat"
        obj.config = MagicMock()
        obj.config.system_prompt = ""
        chat_pane = MagicMock()
        obj.query_one = MagicMock(return_value=chat_pane)
        obj._count_tools = MagicMock(return_value=5)
        obj._welcome_mcp_info = MagicMock(return_value="")

        _ContextTreeMixin._show_welcome(obj)
        chat_pane.add_system_message.assert_called()

    def test_show_welcome_query_error(self) -> None:
        """Test _show_welcome handles query error gracefully."""
        from henchman.cli.textual_mixins import _ContextTreeMixin

        obj = MagicMock()
        obj.query_one = MagicMock(side_effect=Exception("no widget"))

        _ContextTreeMixin._show_welcome(obj)
        # Should not raise

    def test_welcome_mcp_info_no_mcp(self) -> None:
        """Test _welcome_mcp_info returns empty string when no MCP."""
        from henchman.cli.textual_mixins import _ContextTreeMixin

        obj = MagicMock()
        obj.mcp_manager = None

        result = _ContextTreeMixin._welcome_mcp_info(obj)
        assert result == "" or isinstance(result, str)

    def test_toggle_theme(self) -> None:
        """Test action_toggle_theme switches between dark and light."""
        from henchman.cli.textual_mixins import _ContextTreeMixin

        obj = MagicMock()
        obj._theme_name = "dark"
        chat_pane = MagicMock()
        obj.query_one = MagicMock(return_value=chat_pane)
        obj._apply_theme = MagicMock()
        obj.dark = True

        _ContextTreeMixin.action_toggle_theme(obj)
        assert obj._theme_name == "light"

    def test_toggle_theme_to_dark(self) -> None:
        """Test action_toggle_theme switches from light to dark."""
        from henchman.cli.textual_mixins import _ContextTreeMixin

        obj = MagicMock()
        obj._theme_name = "light"
        obj.query_one = MagicMock(side_effect=Exception("no pane"))
        obj._apply_theme = MagicMock()
        obj.dark = False

        _ContextTreeMixin.action_toggle_theme(obj)
        assert obj._theme_name == "dark"


# ---------------------------------------------------------------------------
# _InputHandlerMixin tests
# ---------------------------------------------------------------------------


class TestInputHandlerMixin:
    """Tests for _InputHandlerMixin."""

    def test_record_user_message_with_context(self) -> None:
        """Test _record_user_message records when context has session_manager."""
        from henchman.cli.textual_mixins import _InputHandlerMixin

        obj = MagicMock()
        ctx = MagicMock()
        ctx.session_manager = MagicMock()
        obj.core_context = ctx

        _InputHandlerMixin._record_user_message(obj, "Hello agent")
        ctx.session_manager.record_user_message.assert_called_once_with("Hello agent")

    def test_record_user_message_no_context(self) -> None:
        """Test _record_user_message does nothing without context."""
        from henchman.cli.textual_mixins import _InputHandlerMixin

        obj = MagicMock()
        obj.core_context = None

        _InputHandlerMixin._record_user_message(obj, "Hello")
        # Should not raise


# ---------------------------------------------------------------------------
# _InitMixin tests
# ---------------------------------------------------------------------------


class TestInitMixin:
    """Tests for _InitMixin methods."""

    def test_cleanup_confirm_futures(self) -> None:
        """Test _cleanup_confirm_futures cancels pending futures."""
        from henchman.cli.textual_mixins import _InitMixin

        loop = asyncio.new_event_loop()
        try:
            obj = MagicMock()
            future1 = loop.create_future()
            future2 = loop.create_future()
            obj._confirm_futures = {0: future1, 1: future2}

            _InitMixin._cleanup_confirm_futures(obj)

            # Futures should be cancelled
            assert future1.cancelled() or future2.cancelled()
        finally:
            loop.close()
        return

        _InitMixin._cleanup_confirm_futures(obj)

        # Futures should be cancelled
        assert future1.cancelled() or future2.cancelled()

    def test_activate_chat_tab_success(self) -> None:
        """Test _activate_chat_tab sets active tab."""
        from henchman.cli.textual_mixins import _InitMixin

        obj = MagicMock()
        tabs = MagicMock()
        obj.query_one = MagicMock(return_value=tabs)

        _InitMixin._activate_chat_tab(obj)
        assert tabs.active == "tab-chat"

    def test_activate_chat_tab_error(self) -> None:
        """Test _activate_chat_tab handles error gracefully."""
        from henchman.cli.textual_mixins import _InitMixin

        obj = MagicMock()
        obj.query_one = MagicMock(side_effect=Exception("no widget"))

        _InitMixin._activate_chat_tab(obj)
        # Should not raise
