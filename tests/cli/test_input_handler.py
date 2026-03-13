"""Tests for the InputHandler component."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prompt_toolkit import PromptSession

from henchman.cli.input_handler import InputHandler
from henchman.cli.repl import ReplConfig


class TestInputHandler:
    """Tests for InputHandler class."""

    def test_initialization(self) -> None:
        """Test InputHandler initialization."""
        config = ReplConfig()
        renderer = MagicMock()

        handler = InputHandler(config, renderer)

        assert handler.config == config
        assert handler.renderer == renderer
        assert handler.history_file == Path.home() / ".henchman_history"
        assert handler.prompt_session is None

    def test_initialization_with_custom_history_file(self, tmp_path: Path) -> None:
        """Test InputHandler with custom history file."""
        config = ReplConfig()
        renderer = MagicMock()
        history_file = tmp_path / "custom_history"

        handler = InputHandler(config, renderer, history_file)

        assert handler.history_file == history_file

    def test_initialize_prompt_session(self) -> None:
        """Test initialize_prompt_session method."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        def bottom_toolbar() -> list[tuple[str, str]]:
            return [("style", "text")]

        with patch("henchman.cli.input_handler.create_session") as mock_create:
            mock_session = MagicMock(spec=PromptSession)
            mock_create.return_value = mock_session

            # Mock WordCompleter to capture its creation
            with patch("henchman.cli.input_handler.WordCompleter") as mock_word_completer:
                mock_completer = MagicMock()
                mock_word_completer.return_value = mock_completer

                handler.initialize_prompt_session(bottom_toolbar)

                mock_create.assert_called_once_with(
                    handler.history_file,
                    bottom_toolbar=bottom_toolbar,
                    keybindings=None,
                    completer=mock_completer,
                )

                assert handler.prompt_session == mock_session

    @pytest.mark.asyncio
    async def test_get_input_success(self) -> None:
        """Test get_input method with successful input."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        mock_session = MagicMock(spec=PromptSession)
        mock_session.prompt_async = AsyncMock(return_value="test input")
        handler.prompt_session = mock_session

        # Mock renderer.print_newline if it exists
        if hasattr(renderer, "print_newline"):
            renderer.print_newline = MagicMock()

        result = await handler.get_input()

        assert result == "test input"
        if hasattr(renderer, "print_newline"):
            renderer.print_newline.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_input_without_initialized_session(self) -> None:
        """Test get_input raises RuntimeError when prompt session not initialized."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        with pytest.raises(RuntimeError, match="Prompt session not initialized"):
            await handler.get_input()

    @pytest.mark.asyncio
    async def test_get_input_keyboard_interrupt(self) -> None:
        """Test get_input handles KeyboardInterrupt."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        mock_session = MagicMock(spec=PromptSession)
        mock_session.prompt_async = AsyncMock(side_effect=KeyboardInterrupt())
        handler.prompt_session = mock_session

        if hasattr(renderer, "print_newline"):
            renderer.print_newline = MagicMock()

        with pytest.raises(KeyboardInterrupt):
            await handler.get_input()

    @pytest.mark.asyncio
    async def test_get_input_eof_error(self) -> None:
        """Test get_input handles EOFError."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        mock_session = MagicMock(spec=PromptSession)
        mock_session.prompt_async = AsyncMock(side_effect=EOFError())
        handler.prompt_session = mock_session

        if hasattr(renderer, "print_newline"):
            renderer.print_newline = MagicMock()

        with pytest.raises(EOFError):
            await handler.get_input()

    def test_is_slash_command(self) -> None:
        """Test is_slash_command method."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        assert handler.is_slash_command("/help") is True
        assert handler.is_slash_command("/quit") is True
        assert handler.is_slash_command("help") is False
        assert handler.is_slash_command("") is False
        assert handler.is_slash_command("   ") is False

    @pytest.mark.asyncio
    async def test_expand_at_references(self) -> None:
        """Test expand_at_references method."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        input_text = "test @file.txt input"

        with patch("henchman.cli.input_handler.expand_at_references") as mock_expand:
            mock_expand.return_value = "test expanded content input"

            result = await handler.expand_at_references(input_text)

            mock_expand.assert_called_once_with(input_text)
            assert result == "test expanded content input"

    @pytest.mark.asyncio
    async def test_process_input_empty(self) -> None:
        """Test process_input with empty input."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        processed_input, is_command, should_continue = await handler.process_input("")

        assert processed_input == ""
        assert is_command is False
        assert should_continue is True

    @pytest.mark.asyncio
    async def test_process_input_whitespace(self) -> None:
        """Test process_input with whitespace-only input."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        processed_input, is_command, should_continue = await handler.process_input("   \n\t  ")

        assert processed_input == ""
        assert is_command is False
        assert should_continue is True

    @pytest.mark.asyncio
    async def test_process_input_slash_command(self) -> None:
        """Test process_input with slash command."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        processed_input, is_command, should_continue = await handler.process_input("/help")

        assert processed_input == "/help"
        assert is_command is True
        assert should_continue is True

    @pytest.mark.asyncio
    async def test_process_input_regular_input(self) -> None:
        """Test process_input with regular input (no slash command)."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        with patch.object(handler, "expand_at_references") as mock_expand:
            mock_expand.return_value = "expanded input"

            processed_input, is_command, should_continue = await handler.process_input("test input")

            mock_expand.assert_called_once_with("test input")
            assert processed_input == "expanded input"
            assert is_command is False
            assert should_continue is True

    @pytest.mark.asyncio
    async def test_process_input_with_at_reference(self) -> None:
        """Test process_input with @file reference."""
        config = ReplConfig()
        renderer = MagicMock()
        handler = InputHandler(config, renderer)

        with patch.object(handler, "expand_at_references") as mock_expand:
            mock_expand.return_value = "content from file.txt"

            processed_input, is_command, should_continue = await handler.process_input("@file.txt")

            mock_expand.assert_called_once_with("@file.txt")
            assert processed_input == "content from file.txt"
            assert is_command is False
            assert should_continue is True
