"""Console output and theming for the CLI.

This module provides Rich-based console output with theming support.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax


@dataclass
class Theme:
    """Color theme for CLI output.

    Attributes:
        name: Theme identifier.
        primary: Primary accent color.
        secondary: Secondary accent color.
        success: Success message color.
        warning: Warning message color.
        error: Error message color.
        muted: Muted/dim text style.
    """

    name: str = "dark"
    primary: str = "blue"
    secondary: str = "cyan"
    success: str = "green"
    warning: str = "yellow"
    error: str = "red"
    muted: str = "dim"


# Pre-defined themes
DARK_THEME = Theme(name="dark")
LIGHT_THEME = Theme(
    name="light",
    primary="blue",
    secondary="dark_cyan",
    success="dark_green",
    warning="dark_orange",
    error="dark_red",
    muted="dim",
)


class ThemeManager:
    """Manages available themes and current theme selection.

    Attributes:
        current: The currently active theme.
    """

    def __init__(self) -> None:
        """Initialize the theme manager with default themes."""
        self._themes: dict[str, Theme] = {
            "dark": DARK_THEME,
            "light": LIGHT_THEME,
        }
        self._current: Theme = DARK_THEME

    @property
    def current(self) -> Theme:
        """Get the current theme."""
        return self._current

    def get_theme(self, name: str) -> Theme:
        """Get a theme by name.

        Args:
            name: Theme name.

        Returns:
            The requested theme, or default if not found.
        """
        return self._themes.get(name, DARK_THEME)

    def set_theme(self, name: str) -> None:
        """Set the current theme by name.

        Args:
            name: Theme name to activate.
        """
        self._current = self.get_theme(name)

    def list_themes(self) -> list[str]:
        """List available theme names.

        Returns:
            List of theme names.
        """
        return list(self._themes.keys())

    def register_theme(self, theme: Theme) -> None:
        """Register a custom theme.

        Args:
            theme: Theme to register.
        """
        self._themes[theme.name] = theme


def get_default_theme() -> Theme:
    """Get the default theme.

    Returns:
        The default dark theme.
    """
    return DARK_THEME


class OutputRenderer:
    """Renders styled output to the console.

    Attributes:
        console: Rich Console instance.
        theme: Active color theme.
    """

    def __init__(
        self,
        console: Console | None = None,
        theme: Theme | None = None,
    ) -> None:
        """Initialize the output renderer.

        Args:
            console: Rich Console to use, or creates a new one.
            theme: Theme to use, or uses default.
        """
        self.console = console or Console()
        self.theme = theme or get_default_theme()

    def print(self, text: str, style: str | None = None) -> None:
        """Print text with optional styling.

        Args:
            text: Text to print.
            style: Optional Rich style string.
        """
        self.console.print(text, style=style)

    def success(self, message: str) -> None:
        """Print a success message.

        Args:
            message: Success message text.
        """
        self.console.print(f"[{self.theme.success}]✓[/] {message}")

    def warning(self, message: str) -> None:
        """Print a warning message.

        Args:
            message: Warning message text.
        """
        self.console.print(f"[{self.theme.warning}]⚠[/] {message}")

    def error(self, message: str) -> None:
        """Print an error message.

        Args:
            message: Error message text.
        """
        self.console.print(f"[{self.theme.error}]✗[/] {message}")

    def muted(self, text: str) -> None:
        """Print muted/dim text.

        Args:
            text: Text to print.
        """
        self.console.print(text, style=self.theme.muted)

    def heading(self, text: str) -> None:
        """Print a heading.

        Args:
            text: Heading text.
        """
        self.console.print(f"\n[bold {self.theme.primary}]{text}[/]\n")

    def markdown(self, content: str) -> None:
        """Render markdown content.

        Args:
            content: Markdown text to render.
        """
        md = Markdown(content)
        self.console.print(md)

    def code(self, code: str, language: str = "python") -> None:
        """Print syntax-highlighted code.

        Args:
            code: Code to display.
            language: Programming language for highlighting.
        """
        syntax = Syntax(code, language, theme="monokai")
        self.console.print(syntax)

    def rule(self, title: str | None = None) -> None:
        """Print a horizontal rule.

        Args:
            title: Optional title for the rule.
        """
        if title:
            self.console.rule(title=title)
        else:
            self.console.rule()

    def clear(self) -> None:
        """Clear the console screen."""
        self.console.clear()

    def tool_call(self, name: str, arguments: dict[str, object]) -> None:
        """Display a tool call.

        Args:
            name: Tool name.
            arguments: Tool arguments.
        """
        import json
        args_str = json.dumps(arguments, indent=2)
        content = f"### 🛠️ Tool Call: `{name}`\n\n```json\n{args_str}\n```"
        self.markdown(content)

    def tool_result(
        self, content: str, success: bool = True, error: str | None = None
    ) -> None:
        """Display a tool result.

        Args:
            content: Result content.
            success: Whether the tool execution was successful.
            error: Optional error message if failed.
        """
        # Truncate content if too long
        max_len = 1000
        if len(content) > max_len:
            content = content[:max_len] + "\n... (truncated)"

        status = "Result" if success else "Failed"
        emoji = "✅" if success else "❌"
        title = f"### {emoji} Tool {status}"

        md_content = f"{title}\n\n{content}"
        if error:
            md_content += f"\n\n**Error:** {error}"

        self.markdown(md_content)

    def tool_summary(self, name: str, duration: float | None = None) -> None:
        """Display a summary of tool execution.

        Args:
            name: Tool name.
            duration: Execution duration in seconds.
        """
        msg = f"Executed {name}"
        if duration is not None:
            msg += f" ({duration:.2f}s)"
        self.console.print(msg)
