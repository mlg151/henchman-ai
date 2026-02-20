"""Tests for theme command."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.theme import ThemeCommand
from henchman.cli.console import ThemeManager


@pytest.mark.asyncio
async def test_theme_command_no_args():
    """Test theme command with no arguments shows usage."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = []
    ctx.console = MagicMock()
    ctx.repl = MagicMock()

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    ctx.console.print.assert_called_with("[yellow]Usage:[/] " + cmd.usage)


@pytest.mark.asyncio
async def test_theme_list():
    """Test theme list subcommand."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["list"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.renderer = MagicMock()
    ctx.repl.renderer.renderer = MagicMock()
    ctx.repl.renderer.renderer.theme = MagicMock()
    ctx.repl.renderer.renderer.theme.name = "dark"

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    # Should print available themes
    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_theme_set_valid():
    """Test theme set with valid theme."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["set", "light"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.renderer = MagicMock()
    ctx.repl.renderer.renderer = MagicMock()
    ctx.repl.renderer.renderer.theme = MagicMock()
    ctx.repl.renderer.renderer.theme.name = "dark"
    ctx.repl.settings = MagicMock()
    ctx.repl.settings.ui = MagicMock()

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    # Should set theme and print success message
    # Check that the success message was called (might be called with other messages too)
    ctx.console.print.assert_any_call("[green]Theme set to:[/] light")


@pytest.mark.asyncio
async def test_theme_set_invalid():
    """Test theme set with invalid theme falls back to default."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["set", "invalid-theme"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.renderer = MagicMock()
    ctx.repl.renderer.renderer = MagicMock()
    ctx.repl.renderer.renderer.theme = MagicMock()
    ctx.repl.renderer.renderer.theme.name = "dark"
    ctx.repl.settings = MagicMock()
    ctx.repl.settings.ui = MagicMock()

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    # Should warn about invalid theme and fall back
    ctx.console.print.assert_any_call("[yellow]Warning:[/] Theme 'invalid-theme' not found")
    ctx.console.print.assert_any_call("[green]Theme set to:[/] dark")


@pytest.mark.asyncio
async def test_theme_set_no_args():
    """Test theme set with no theme name."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["set"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    # Check that error message was called (might be called with usage too)
    ctx.console.print.assert_any_call("[red]Error:[/] Theme name required")


@pytest.mark.asyncio
async def test_theme_preview_valid():
    """Test theme preview with valid theme."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["preview", "light"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.renderer = MagicMock()
    ctx.repl.renderer.renderer = MagicMock()
    ctx.repl.renderer.renderer.theme = MagicMock()
    ctx.repl.renderer.renderer.theme.name = "dark"

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    # Should print preview heading
    ctx.console.print.assert_any_call("\n[bold blue]Preview of 'light' theme[/]\n")


@pytest.mark.asyncio
async def test_theme_preview_invalid():
    """Test theme preview with invalid theme."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["preview", "invalid-theme"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.renderer = MagicMock()
    ctx.repl.renderer.renderer = MagicMock()
    ctx.repl.renderer.renderer.theme = MagicMock()
    ctx.repl.renderer.renderer.theme.name = "dark"

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    # Check that error message was called (might be called with available themes too)
    ctx.console.print.assert_any_call("[red]Error:[/] Theme 'invalid-theme' not found")


@pytest.mark.asyncio
async def test_theme_preview_no_args():
    """Test theme preview with no theme name."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["preview"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    # Check that error message was called (might be called with usage too)
    ctx.console.print.assert_any_call("[red]Error:[/] Theme name required")


@pytest.mark.asyncio
async def test_theme_create():
    """Test theme create subcommand (stub)."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["create", "custom-theme"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    # Check that warning message was called (might be called with follow-up message too)
    ctx.console.print.assert_any_call("[yellow]Custom theme creation is not yet implemented.[/]")


@pytest.mark.asyncio
async def test_theme_unknown_subcommand():
    """Test theme with unknown subcommand."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["unknown"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    # Check that error message was called (might be called with usage too)
    ctx.console.print.assert_any_call("[red]Unknown subcommand: unknown[/]")


def test_theme_command_properties():
    """Test theme command properties."""
    cmd = ThemeCommand()
    assert cmd.name == "theme"
    assert "Manage UI themes" in cmd.description
    assert "/theme <subcommand>" in cmd.usage


def test_get_theme_manager_with_repl():
    """Test _get_theme_manager with REPL instance."""
    cmd = ThemeCommand()

    # Mock REPL with renderer
    mock_repl = MagicMock()
    mock_repl.renderer = MagicMock()
    mock_repl.renderer.renderer = MagicMock()
    mock_repl.renderer.renderer.theme = MagicMock()
    mock_repl.renderer.renderer.theme.name = "light"

    theme_manager = cmd._get_theme_manager(mock_repl)
    assert isinstance(theme_manager, ThemeManager)
    assert theme_manager.current.name == "light"


def test_get_theme_manager_without_repl():
    """Test _get_theme_manager without REPL instance."""
    cmd = ThemeCommand()
    theme_manager = cmd._get_theme_manager(None)
    assert isinstance(theme_manager, ThemeManager)
    assert theme_manager.current.name == "dark"


def test_get_theme_manager_with_incomplete_repl():
    """Test _get_theme_manager with REPL missing renderer attributes."""
    cmd = ThemeCommand()

    # Mock REPL without renderer.renderer.theme
    mock_repl = MagicMock()
    mock_repl.renderer = MagicMock()
    mock_repl.renderer.renderer = MagicMock()
    # No theme attribute

    theme_manager = cmd._get_theme_manager(mock_repl)
    assert isinstance(theme_manager, ThemeManager)
    assert theme_manager.current.name == "dark"


@pytest.mark.asyncio
async def test_theme_set_updates_renderer():
    """Test theme set updates REPL renderer theme."""
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["set", "light"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()

    # Create a real theme manager for the REPL renderer
    from henchman.cli.console import OutputRenderer, Theme
    from henchman.cli.ui_renderer import UIRenderer

    # Create renderer with dark theme
    dark_theme = Theme(name="dark")
    output_renderer = OutputRenderer(console=ctx.console, theme=dark_theme)
    renderer = UIRenderer(console=ctx.console, renderer=output_renderer)

    ctx.repl.renderer = renderer
    ctx.repl.settings = MagicMock()
    ctx.repl.settings.ui = MagicMock()

    cmd = ThemeCommand()
    await cmd.execute(ctx)

    # Theme should be updated to light
    assert ctx.repl.renderer.renderer.theme.name == "light"
    # Check that success message was called (might be called with save message too)
    ctx.console.print.assert_any_call("[green]Theme set to:[/] light")
