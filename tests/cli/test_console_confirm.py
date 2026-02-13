"""Tests for console confirmation method."""

from unittest.mock import Mock, patch

import pytest

from henchman.cli.console import OutputRenderer


@pytest.mark.asyncio
async def test_confirm_method():
    """Test the confirm_tool_execution method in OutputRenderer."""
    console = Mock()
    theme = Mock()
    theme.muted = "dim"
    output_renderer = OutputRenderer(console=console, theme=theme)

    # Mock the Confirm.ask to return True
    with patch("rich.prompt.Confirm") as mock_confirm:
        mock_confirm.ask.return_value = True

        # Test confirmation
        result = await output_renderer.confirm_tool_execution("Are you sure?")

        # Verify Confirm.ask was called with correct parameters
        mock_confirm.ask.assert_called_once_with("Are you sure?", console=console)
        assert result is True


@pytest.mark.asyncio
async def test_confirm_method_false():
    """Test the confirm_tool_execution method returning False."""
    console = Mock()
    theme = Mock()
    theme.muted = "dim"
    output_renderer = OutputRenderer(console=console, theme=theme)

    # Mock the Confirm.ask to return False
    with patch("rich.prompt.Confirm") as mock_confirm:
        mock_confirm.ask.return_value = False

        # Test confirmation
        result = await output_renderer.confirm_tool_execution("Are you sure?")

        # Verify Confirm.ask was called with correct parameters
        mock_confirm.ask.assert_called_once_with("Are you sure?", console=console)
        assert result is False


@pytest.mark.asyncio
async def test_confirm_with_different_messages():
    """Test confirm_tool_execution method with different message formats."""
    console = Mock()
    theme = Mock()
    theme.muted = "dim"
    output_renderer = OutputRenderer(console=console, theme=theme)

    with patch("rich.prompt.Confirm") as mock_confirm:
        mock_confirm.ask.return_value = True

        # Test with different messages
        messages = [
            "Confirm action?",
            "Do you want to proceed?",
            "Delete file?",
            "Execute command?",
        ]

        for message in messages:
            mock_confirm.ask.reset_mock()
            result = await output_renderer.confirm_tool_execution(message)
            mock_confirm.ask.assert_called_once_with(message, console=console)
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
