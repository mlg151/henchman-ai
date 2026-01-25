"""Tests for console output and theming."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from henchman.cli.console import (
    OutputRenderer,
    Theme,
    ThemeManager,
    get_default_theme,
)


class TestTheme:
    """Tests for Theme dataclass."""

    def test_default_theme_values(self) -> None:
        """Test default theme has expected colors."""
        theme = Theme()
        assert theme.name == "dark"
        assert theme.primary == "blue"
        assert theme.secondary == "cyan"
        assert theme.success == "green"
        assert theme.warning == "yellow"
        assert theme.error == "red"
        assert theme.muted == "dim"

    def test_custom_theme(self) -> None:
        """Test creating a custom theme."""
        theme = Theme(
            name="custom",
            primary="magenta",
            secondary="white",
            success="bright_green",
            warning="orange3",
            error="red1",
            muted="grey50",
        )
        assert theme.name == "custom"
        assert theme.primary == "magenta"


class TestThemeManager:
    """Tests for ThemeManager class."""

    def test_default_theme(self) -> None:
        """Test that default theme is 'dark'."""
        manager = ThemeManager()
        assert manager.current.name == "dark"

    def test_get_theme_dark(self) -> None:
        """Test getting the dark theme."""
        manager = ThemeManager()
        theme = manager.get_theme("dark")
        assert theme.name == "dark"
        assert theme.primary == "blue"

    def test_get_theme_light(self) -> None:
        """Test getting the light theme."""
        manager = ThemeManager()
        theme = manager.get_theme("light")
        assert theme.name == "light"
        assert theme.primary == "blue"

    def test_get_theme_unknown_returns_default(self) -> None:
        """Test that unknown theme returns default."""
        manager = ThemeManager()
        theme = manager.get_theme("nonexistent")
        assert theme.name == "dark"

    def test_set_theme(self) -> None:
        """Test setting the current theme."""
        manager = ThemeManager()
        manager.set_theme("light")
        assert manager.current.name == "light"

    def test_list_themes(self) -> None:
        """Test listing available themes."""
        manager = ThemeManager()
        themes = manager.list_themes()
        assert "dark" in themes
        assert "light" in themes

    def test_register_custom_theme(self) -> None:
        """Test registering a custom theme."""
        manager = ThemeManager()
        custom = Theme(name="my_theme", primary="purple")
        manager.register_theme(custom)
        assert "my_theme" in manager.list_themes()
        theme = manager.get_theme("my_theme")
        assert theme.primary == "purple"


class TestGetDefaultTheme:
    """Tests for get_default_theme function."""

    def test_returns_theme(self) -> None:
        """Test that get_default_theme returns a Theme."""
        theme = get_default_theme()
        assert isinstance(theme, Theme)
        assert theme.name == "dark"


class TestOutputRenderer:
    """Tests for OutputRenderer class."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a test console that writes to a string."""
        return Console(file=StringIO(), force_terminal=True, width=80)

    @pytest.fixture
    def renderer(self, console: Console) -> OutputRenderer:
        """Create an OutputRenderer with test console."""
        return OutputRenderer(console=console)

    def test_print_text(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing plain text."""
        renderer.print("Hello, world!")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Hello, world!" in output

    def test_print_styled(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing styled text."""
        renderer.print("Success!", style="green")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Success!" in output

    def test_print_success(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing success message."""
        renderer.success("Operation completed")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Operation completed" in output
        assert "✓" in output

    def test_print_warning(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing warning message."""
        renderer.warning("Be careful")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Be careful" in output
        assert "⚠" in output

    def test_print_error(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing error message."""
        renderer.error("Something went wrong")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Something went wrong" in output
        assert "✗" in output

    def test_print_muted(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing muted text."""
        renderer.muted("Debug info")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Debug info" in output

    def test_print_info(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing info message."""
        renderer.info("Information")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Information" in output
        assert "ℹ" in output

    def test_print_heading(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing a heading."""
        renderer.heading("Section Title")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Section Title" in output

    def test_print_markdown(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing markdown content."""
        renderer.markdown("# Hello\n\nThis is **bold** text.")
        output = console.file.getvalue()  # type: ignore[union-attr]
        # Markdown is rendered, so check for content
        assert "Hello" in output or "bold" in output

    def test_print_code(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing code block."""
        renderer.code("print('hello')", language="python")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "print" in output

    def test_print_rule(self, renderer: OutputRenderer, console: Console) -> None:
        """Test printing a horizontal rule."""
        renderer.rule()
        output = console.file.getvalue()  # type: ignore[union-attr]
        # Rule produces line characters
        assert len(output) > 0

    def test_print_rule_with_title(
        self, renderer: OutputRenderer, console: Console
    ) -> None:
        """Test printing a rule with title."""
        renderer.rule(title="Separator")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Separator" in output

    def test_clear(self, renderer: OutputRenderer) -> None:
        """Test clear method exists and is callable."""
        # Just verify it doesn't raise
        renderer.clear()

    def test_custom_theme(self, console: Console) -> None:
        """Test renderer with custom theme."""
        theme = Theme(name="custom", success="bright_green")
        renderer = OutputRenderer(console=console, theme=theme)
        assert renderer.theme.name == "custom"

    def test_default_console_creation(self) -> None:
        """Test that renderer creates a console if not provided."""
        renderer = OutputRenderer()
        assert renderer.console is not None
        assert isinstance(renderer.console, Console)
