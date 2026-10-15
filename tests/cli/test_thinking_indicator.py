"""Tests for thinking indicator feature in UIRenderer."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from rich.console import Console
from rich.status import Status

from henchman.cli.ui_renderer import UIRenderer


class TestThinkingIndicator:
    """Tests for thinking indicator functionality."""

    def test_thinking_indicator_initialization(self) -> None:
        """Test that UIRenderer initializes without thinking indicator by default."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        # Should have thinking indicator attributes but inactive initially
        assert hasattr(renderer, "_thinking_status")
        assert renderer._thinking_status is None
        assert hasattr(renderer, "_is_thinking")
        assert renderer._is_thinking is False

    def test_start_thinking(self) -> None:
        """Test starting a thinking indicator."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        # Mock the console.status method
        mock_status = MagicMock(spec=Status)
        with patch.object(console, "status", return_value=mock_status) as mock_status_method:
            renderer.start_thinking("Processing your request...")

            # Should create a status with thinking message
            mock_status_method.assert_called_once_with(
                "[dim]Thinking…[/] Processing your request...", spinner="dots"
            )

            # Should start the status
            mock_status.__enter__.assert_called_once()

            # Should store the status
            assert renderer._thinking_status == mock_status
            assert renderer._is_thinking is True

    def test_start_thinking_default_message(self) -> None:
        """Test starting thinking indicator with default message."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        mock_status = MagicMock(spec=Status)
        with patch.object(console, "status", return_value=mock_status):
            renderer.start_thinking()

            # Should use default message
            console.status.assert_called_once_with("[dim]Thinking…[/]", spinner="dots")

    def test_stop_thinking(self) -> None:
        """Test stopping a thinking indicator."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        # Mock a status
        mock_status = MagicMock(spec=Status)
        renderer._thinking_status = mock_status
        renderer._is_thinking = True

        renderer.stop_thinking()

        # Should stop the status
        mock_status.__exit__.assert_called_once_with(None, None, None)

        # Should clear the attributes
        assert renderer._thinking_status is None
        assert renderer._is_thinking is False

    def test_stop_thinking_when_not_thinking(self) -> None:
        """Test stopping thinking when no indicator is active."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        # Should not raise an error
        renderer.stop_thinking()

        # Attributes should be None/False
        assert renderer._thinking_status is None
        assert renderer._is_thinking is False

    def test_thinking_context_manager(self) -> None:
        """Test thinking indicator as a context manager."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        mock_status = MagicMock(spec=Status)

        with patch.object(console, "status", return_value=mock_status):
            # Use as context manager
            with renderer.thinking_context("Analyzing code..."):
                assert renderer.is_thinking
                mock_status.__enter__.assert_called_once()

            # Should have exited
            mock_status.__exit__.assert_called_once_with(None, None, None)

    def test_thinking_context_manager_default_message(self) -> None:
        """Test thinking context manager with default message."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        mock_status = MagicMock(spec=Status)

        with patch.object(console, "status", return_value=mock_status):
            with renderer.thinking_context():
                assert renderer.is_thinking
                mock_status.__enter__.assert_called_once()

            mock_status.__exit__.assert_called_once_with(None, None, None)

    def test_is_thinking_property(self) -> None:
        """Test the is_thinking property."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        # Initially not thinking
        assert renderer.is_thinking is False

        # Set thinking
        renderer._is_thinking = True
        assert renderer.is_thinking is True

        # Clear thinking
        renderer._is_thinking = False
        assert renderer.is_thinking is False

    def test_thinking_with_custom_spinner(self) -> None:
        """Test thinking indicator with custom spinner."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        mock_status = MagicMock(spec=Status)
        with patch.object(console, "status", return_value=mock_status):
            renderer.start_thinking("Processing", spinner="line")

            console.status.assert_called_once_with("[dim]Thinking…[/] Processing", spinner="line")

    def test_thinking_detail_is_rendered_as_plain_text(self) -> None:
        """Status details must not be able to inject Rich styling."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        mock_status = MagicMock(spec=Status)
        with patch.object(console, "status", return_value=mock_status):
            renderer.start_thinking("[red]spoofed status[/]")

            console.status.assert_called_once_with(
                "[dim]Thinking…[/] \\[red]spoofed status\\[/]",
                spinner="dots",
            )

    def test_thinking_context_manager_exception_handling(self) -> None:
        """Test that thinking indicator stops even if exception occurs."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        mock_status = MagicMock(spec=Status)

        with patch.object(console, "status", return_value=mock_status):
            try:
                with renderer.thinking_context("Working..."):
                    raise ValueError("Test error")
            except ValueError:
                pass

            # Should have stopped the status even with exception
            mock_status.__exit__.assert_called_once()

    def test_multiple_start_thinking_calls(self) -> None:
        """Test that starting thinking multiple times handles previous indicator."""
        console = Console(file=StringIO())
        renderer = UIRenderer(console=console)

        mock_status1 = MagicMock(spec=Status)
        mock_status2 = MagicMock(spec=Status)

        with patch.object(console, "status", side_effect=[mock_status1, mock_status2]):
            # First thinking indicator
            renderer.start_thinking("First thought")
            assert renderer._thinking_status == mock_status1
            assert renderer._is_thinking is True

            # Second thinking indicator should stop first
            renderer.start_thinking("Second thought")
            mock_status1.__exit__.assert_called_once_with(None, None, None)

            # Should now be using second status
            assert renderer._thinking_status == mock_status2
            assert renderer._is_thinking is True
