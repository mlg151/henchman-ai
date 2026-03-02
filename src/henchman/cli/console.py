"""Console output and theming for the CLI.

This module provides Rich-based console output with theming support.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

import anyio
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

# Safety limit: truncate content before Rich parses it to prevent
# excessive memory / CPU usage on pathologically large payloads.
_MAX_MARKDOWN_LEN = 200_000


class DiffParams(NamedTuple):
    """Parameters for diff rendering.

    Attributes:
        old: Old content string.
        new: New content string.
        filename: Filename for context.
    """

    old: str
    new: str
    filename: str = ""


@dataclass
class StatusMessageParams:
    """Parameters for status message rendering.

    Attributes:
        message: Message text.
        style: Theme style name (success, primary, warning, error).
        icon: Unicode icon for normal mode.
        accessible_icon: Text icon for accessible mode.
    """

    message: str
    style: str
    icon: str
    accessible_icon: str


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

    def with_overrides(self, overrides: dict[str, str] | None = None) -> Theme:
        """Create a new theme with style overrides applied.

        Args:
            overrides: Optional style overrides.

        Returns:
            New Theme instance with overrides applied.
        """
        if not overrides:
            return self

        return Theme(
            name=self.name,
            primary=overrides.get("primary", self.primary),
            secondary=overrides.get("secondary", self.secondary),
            success=overrides.get("success", self.success),
            warning=overrides.get("warning", self.warning),
            error=overrides.get("error", self.error),
            muted=overrides.get("muted", self.muted),
        )


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
SOLARIZED_DARK_THEME = Theme(
    name="solarized-dark",
    primary="cyan",
    secondary="blue",
    success="green",
    warning="yellow",
    error="red",
    muted="bright_black",
)
SOLARIZED_LIGHT_THEME = Theme(
    name="solarized-light",
    primary="blue",
    secondary="cyan",
    success="green",
    warning="yellow",
    error="red",
    muted="bright_black",
)
MONOKAI_THEME = Theme(
    name="monokai",
    primary="magenta",
    secondary="cyan",
    success="green",
    warning="yellow",
    error="red",
    muted="white",
)
DRACULA_THEME = Theme(
    name="dracula",
    primary="purple",
    secondary="pink",
    success="green",
    warning="yellow",
    error="red",
    muted="bright_white",
)
HIGH_CONTRAST_DARK_THEME = Theme(
    name="high-contrast-dark",
    primary="bright_white",
    secondary="bright_cyan",
    success="bright_green",
    warning="bright_yellow",
    error="bright_red",
    muted="white",
)
HIGH_CONTRAST_LIGHT_THEME = Theme(
    name="high-contrast-light",
    primary="black",
    secondary="blue",
    success="green",
    warning="yellow",
    error="red",
    muted="bright_black",
)

THEMES: dict[str, Theme] = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
    "solarized-dark": SOLARIZED_DARK_THEME,
    "solarized-light": SOLARIZED_LIGHT_THEME,
    "monokai": MONOKAI_THEME,
    "dracula": DRACULA_THEME,
    "high-contrast-dark": HIGH_CONTRAST_DARK_THEME,
    "high-contrast-light": HIGH_CONTRAST_LIGHT_THEME,
}


def get_theme(name: str = "dark", overrides: dict[str, str] | None = None) -> Theme:
    """Get a theme by name with optional overrides.

    Args:
        name: Theme name.
        overrides: Optional style overrides.

    Returns:
        Theme object.
    """
    base_theme = THEMES.get(name, DARK_THEME)
    return base_theme.with_overrides(overrides)


class ThemeManager:
    """Manages available themes and current theme selection.

    Attributes:
        current: The currently active theme.
    """

    def __init__(self) -> None:
        """Initialize the theme manager with default themes."""
        self._themes = THEMES.copy()
        self._current: Theme = DARK_THEME

    @property
    def current(self) -> Theme:
        """Get the current theme."""
        return self._current

    def get_theme(self, name: str, overrides: dict[str, str] | None = None) -> Theme:
        """Get a theme by name with optional overrides.

        Args:
            name: Theme name.
            overrides: Optional style overrides.

        Returns:
            The requested theme with overrides applied, or default if not found.
        """
        base_theme = self._themes.get(name, DARK_THEME)
        return base_theme.with_overrides(overrides)

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


def get_default_theme(overrides: dict[str, str] | None = None) -> Theme:
    """Get the default theme.

    Args:
        overrides: Optional style overrides.

    Returns:
        The default theme.
    """
    return get_theme("dark", overrides)


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
        accessible_mode: bool = False,
        style_overrides: dict[str, str] | None = None,
        layout_settings: object | None = None,  # Avoid circular import, pass as object or dict
    ) -> None:
        """Initialize the output renderer.

        Args:
            console: Rich Console to use, or creates a new one.
            theme: Theme to use, or uses default.
            accessible_mode: Whether to enable high-accessibility mode.
            style_overrides: Optional style overrides.
            layout_settings: Optional LayoutSettings object.
        """
        self.console = console or Console()
        self.accessible_mode = accessible_mode
        self.layout_settings = layout_settings
        self.theme: Theme = theme or get_theme("dark", overrides=style_overrides)

        if theme is None:
            # Already set above with overrides
            pass
        elif style_overrides:
            # If theme provided, apply overrides to it
            self.theme = self.theme.with_overrides(style_overrides)

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
        self._print_status_message(
            StatusMessageParams(message=message, style="success", icon="✓", accessible_icon="[OK]")
        )

    def info(self, message: str) -> None:
        """Print an info message.

        Args:
            message: Info message text.
        """
        self._print_status_message(
            StatusMessageParams(
                message=message, style="primary", icon="ℹ", accessible_icon="[INFO]"
            )
        )

    def warning(self, message: str) -> None:
        """Print a warning message.

        Args:
            message: Warning message text.
        """
        self._print_status_message(
            StatusMessageParams(
                message=message, style="warning", icon="⚠", accessible_icon="[WARN]"
            )
        )

    def error(self, message: str) -> None:
        """Print an error message.

        Args:
            message: Error message text.
        """
        self._print_status_message(
            StatusMessageParams(message=message, style="error", icon="✗", accessible_icon="[ERR]")
        )

    def _print_status_message(self, params: StatusMessageParams) -> None:
        """Print a status message with consistent formatting.

        Args:
            params: Status message parameters.
        """
        prefix = params.accessible_icon if self.accessible_mode else params.icon
        color = getattr(self.theme, params.style)
        self.console.print(f"[{color}]{prefix}[/] {escape(params.message)}")

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
        self.console.print(f"\n[bold {self.theme.primary}]{escape(text)}[/]\n")

    def markdown(self, content: str) -> None:
        """Render markdown content.

        Args:
            content: Markdown text to render.
        """
        if not content:
            return
        if len(content) > _MAX_MARKDOWN_LEN:
            content = content[:_MAX_MARKDOWN_LEN]
            # Close any orphaned code fences
            if content.count("```") % 2 != 0:
                content += "\n```"
            content += "\n\n*(content truncated)*"
        md = Markdown(content)
        self.console.print(md)

    def code(self, code: str, language: str = "python") -> None:
        """Print syntax-highlighted code.

        Args:
            code: Code to display.
            language: Programming language for highlighting.
        """
        if not code:
            return
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
        # Escape backticks in tool name to prevent markdown code-fence breakout
        safe_name = name.replace("`", "\\`")
        content = f"### 🛠️ Tool Call: `{safe_name}`\n\n```json\n{args_str}\n```"
        self.markdown(content)

    def tool_result(self, content: str, success: bool = True, error: str | None = None) -> None:
        """Display a tool result.

        Args:
            content: Result content.
            success: Whether the tool execution was successful.
            error: Optional error message if failed.
        """
        # Truncate content if too long
        max_len = 1000
        if len(content) > max_len:
            content = content[:max_len]
            # Close unclosed code fences to prevent rendering corruption
            if content.count("```") % 2 != 0:
                content += "\n```"
            content += "\n... (truncated)"

        status = "Result" if success else "Failed"
        if self.accessible_mode:
            emoji = "[OK]" if success else "[ERR]"
        else:
            emoji = "✅" if success else "❌"
        title = f"### {emoji} Tool {status}"

        md_content = f"{title}\n\n{content}"
        if error:
            md_content += f"\n\n**Error:** {error}"

        self.markdown(md_content)

    def table(self, data: list[dict[str, object]], title: str | None = None) -> None:
        """Render data as a table.

        Args:
            data: List of dictionaries to display.
            title: Optional table title.
        """
        if not data:
            self.muted("No data to display")
            return

        if (
            self.layout_settings
            and hasattr(self.layout_settings, "compact_tables")
            and self.layout_settings.compact_tables
        ):
            table_box = box.MINIMAL
        else:
            table_box = box.ASCII if self.accessible_mode else box.HEAVY_HEAD

        table = Table(
            title=title, show_header=True, header_style=f"bold {self.theme.primary}", box=table_box
        )

        # Add columns from first row keys
        for key in data[0]:
            table.add_column(str(key))

        # Add rows
        for row in data:
            table.add_row(*[str(v) for v in row.values()])

        self.console.print(table)

    def tree(self, root_name: str, items: list[tuple[str, str]]) -> None:
        """Render hierarchical data as a tree.

        Args:
            root_name: Name of the root node.
            items: List of (path, value) tuples. Path is slash-separated.
        """
        tree = Tree(f"[bold {self.theme.primary}]{root_name}[/]")

        for path, value in items:
            current = tree
            parts = path.split("/")

            for part in parts[:-1]:
                # Find or create branch
                found = False
                for child in current.children:
                    if str(child.label) == part:
                        current = child
                        found = True
                        break

                if not found:
                    current = current.add(f"[{self.theme.secondary}]{part}[/]")

            # Add leaf with value
            current.add(f"{parts[-1]}: [bold]{value}[/]")

        self.console.print(tree)

    def diff(self, old: str, new: str, filename: str = "") -> None:
        """Render diff between old and new content.

        Args:
            old: Old content string.
            new: New content string.
            filename: Filename for context.
        """
        params = DiffParams(old, new, filename)
        self._render_diff(params)

    def _render_diff(self, params: DiffParams) -> None:
        """Render diff using DiffParams object.

        Args:
            params: Diff parameters.
        """
        import difflib

        diff_lines = difflib.unified_diff(
            params.old.splitlines(keepends=True),
            params.new.splitlines(keepends=True),
            fromfile=f"a/{params.filename}",
            tofile=f"b/{params.filename}",
        )
        diff_text = "".join(diff_lines)

        if diff_text:
            syntax = Syntax(diff_text, "diff", theme="monokai")
            self.console.print(syntax)
        else:
            self.success("No differences found")

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

    def print_agent_content(self, content: str) -> None:
        """Display content from the agent.

        Args:
            content: Content string.
        """
        self.console.print(content, end="")

    def agent_content(self, content: str) -> None:
        """Display content from the agent (alias for print_agent_content).

        Args:
            content: Content string.
        """
        self.print_agent_content(content)

    def thinking(self, content: str) -> None:
        """Display thinking process.

        Args:
            content: Thinking content.
        """
        # Escape content to prevent rich markup interpretation
        # Note: We should eventually render markdown properly, but for now
        # escape to show raw content including markdown symbols
        from rich.markup import escape

        self.console.print(escape(content), style=self.theme.muted, end="")

    async def confirm_tool_execution(self, message: str) -> bool:
        """Ask user for confirmation.

        Args:
            message: Confirmation message.

        Returns:
            True if confirmed.
        """
        from rich.prompt import Confirm

        return await anyio.to_thread.run_sync(lambda: Confirm.ask(message, console=self.console))


class AsyncOutputRenderer:
    """Async wrapper for OutputRenderer."""

    def __init__(self, renderer: OutputRenderer) -> None:
        """Initialize the async renderer.

        Args:
            renderer: Sync OutputRenderer instance.
        """
        self.renderer = renderer
        self._async_methods: dict[str, Callable[..., object]] = {}

    def __getattr__(self, name: str) -> Callable[..., object]:
        """Dynamically create async wrappers for OutputRenderer methods.

        Args:
            name: Method name to look up.

        Returns:
            Async wrapper function for the method.

        Raises:
            AttributeError: If the method doesn't exist on OutputRenderer.
        """
        # Check if method exists on the renderer
        if not hasattr(self.renderer, name):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        # Get the sync method
        sync_method = getattr(self.renderer, name)

        # Skip private methods
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        # Special handling for diff method
        if name == "diff":

            async def async_diff(old: str, new: str, filename: str = "") -> None:
                params = DiffParams(old, new, filename)
                await anyio.to_thread.run_sync(self.renderer._render_diff, params)

            self._async_methods[name] = async_diff
            return async_diff

        # Create async wrapper for other methods
        async def async_wrapper(*args: object, **kwargs: object) -> object:
            # Create a wrapper function that captures args and kwargs
            def sync_wrapper() -> object:
                return sync_method(*args, **kwargs)

            return await anyio.to_thread.run_sync(sync_wrapper)

        # Cache the wrapper
        self._async_methods[name] = async_wrapper
        return async_wrapper
