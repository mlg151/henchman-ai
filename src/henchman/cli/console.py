"""Console output and theming for the CLI.

This module provides Rich-based console output with theming support.
"""

from __future__ import annotations

import difflib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, NamedTuple, ParamSpec, TypeVar

import anyio
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

# Type variables for generic async wrappers
P = ParamSpec("P")  # For parameters
R = TypeVar("R")  # For return values
AsyncMethod = Callable[P, Awaitable[R]]
SyncMethod = Callable[P, R]

# Self type for Python < 3.11 compatibility
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

# Safety limit: truncate content before Rich parses it to prevent
# excessive memory / CPU usage on pathologically large payloads.
_MAX_MARKDOWN_LEN = 200_000
# Maximum length for tool result content before truncation
_MAX_TOOL_RESULT_LEN = 1000
# Constants for diff argument parsing
_MIN_DIFF_ARGS = 2
_MAX_DIFF_ARGS = 3


def list_dict_keys(items_dict: dict[str, Any]) -> list[str]:
    """Utility function to list keys from a dictionary.

    Args:
        items_dict: Dictionary to list keys from.

    Returns:
        List of dictionary keys.
    """
    return list(items_dict.keys())


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


@dataclass(frozen=True)
class StatusTypeConfig:
    """Configuration for a status message type.

    Attributes:
        style: Rich style string for the status.
        icon: Unicode icon for the status.
        accessible_icon: Text-based icon for accessibility mode.
    """

    style: str
    icon: str
    accessible_icon: str


class StatusType(Enum):
    """Status message types with their styling configuration."""

    SUCCESS = StatusTypeConfig("success", "✓", "[OK]")
    INFO = StatusTypeConfig("primary", "ℹ", "[INFO]")  # noqa: RUF001
    WARNING = StatusTypeConfig("warning", "⚠", "[WARN]")
    ERROR = StatusTypeConfig("error", "✗", "[ERR]")

    @property
    def style(self: Self) -> str:
        """Get the style for this status type."""
        return self.value.style  # type: ignore[no-any-return]

    @property
    def icon(self: Self) -> str:
        """Get the icon for this status type."""
        return self.value.icon  # type: ignore[no-any-return]

    @property
    def accessible_icon(self: Self) -> str:
        """Get the accessible icon for this status type."""
        return self.value.accessible_icon  # type: ignore[no-any-return]


@dataclass
class StatusMessageParams:
    """Parameters for status message rendering.

    Attributes:
        message: Message text.
        status_type: Type of status message.
    """

    message: str
    status_type: StatusType


@dataclass
class OutputRendererConfig:
    """Configuration for OutputRenderer initialization.

    Attributes:
        console: Rich Console to use, or creates a new one.
        theme: Theme to use, or uses default.
        accessible_mode: Whether to enable high-accessibility mode.
        style_overrides: Optional style overrides.
        layout_settings: Optional LayoutSettings object.
    """

    console: Console | None = None
    theme: Theme | None = None
    accessible_mode: bool = False
    style_overrides: dict[str, str] | None = None
    layout_settings: Any | None = None  # Avoid circular import, pass as object or dict

    def get_resolved_theme(self: Self) -> Theme:
        """Get the resolved theme based on configuration.

        Returns:
            The resolved Theme object.
        """
        if self.theme is None:
            return get_theme("dark", overrides=self.style_overrides)
        if self.style_overrides:
            return self.theme.with_overrides(self.style_overrides)
        return self.theme


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

    def with_overrides(self: Self, overrides: dict[str, str] | None = None) -> Theme:
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
    return _get_theme_from_dict(THEMES, name, overrides)


def _get_theme_from_dict(
    themes_dict: dict[str, Theme],
    name: str,
    overrides: dict[str, str] | None = None,
) -> Theme:
    """Get a theme from a dictionary with optional overrides.

    Args:
        themes_dict: Dictionary of theme names to Theme objects.
        name: Theme name.
        overrides: Optional style overrides.

    Returns:
        Theme object with overrides applied.
    """
    base_theme = themes_dict.get(name, DARK_THEME)
    return base_theme.with_overrides(overrides)


class ThemeManager:
    """Manages available themes and current theme selection.

    Attributes:
        current: The currently active theme.
    """

    def __init__(self: Self) -> None:
        """Initialize the theme manager with default themes."""
        self._themes = THEMES.copy()
        self._current: Theme = DARK_THEME

    @property
    def current(self: Self) -> Theme:
        """Get the current theme."""
        return self._current

    def get_theme(self: Self, name: str, overrides: dict[str, str] | None = None) -> Theme:
        """Get a theme by name with optional overrides.

        Args:
            name: Theme name.
            overrides: Optional style overrides.

        Returns:
            The requested theme with overrides applied, or default if not found.
        """
        return _get_theme_from_dict(self._themes, name, overrides)

    def set_theme(self: Self, name: str) -> None:
        """Set the current theme by name.

        Args:
            name: Theme name to activate.
        """
        self._current = self.get_theme(name)

    def list_themes(self: Self) -> list[str]:
        """List available theme names.

        Returns:
            List of theme names.
        """
        return list_dict_keys(self._themes)

    def register_theme(self: Self, theme: Theme) -> None:
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
        self: Self,
        console: Console | None = None,
        theme: Theme | None = None,
        *,
        accessible_mode: bool = False,
        style_overrides: dict[str, str] | None = None,
        layout_settings: Any | None = None,  # Avoid circular import, pass as object or dict
    ) -> None:
        """Initialize the output renderer.

        Args:
            console: Rich Console to use, or creates a new one.
            theme: Theme to use, or uses default.
            accessible_mode: Whether to enable high-accessibility mode.
            style_overrides: Optional style overrides.
            layout_settings: Optional LayoutSettings object.
        """
        self._initialize_from_config(
            OutputRendererConfig(
                console=console,
                theme=theme,
                accessible_mode=accessible_mode,
                style_overrides=style_overrides,
                layout_settings=layout_settings,
            ),
        )

    def _initialize_from_config(self: Self, config: OutputRendererConfig) -> None:
        """Initialize renderer from configuration object.

        Args:
            config: OutputRendererConfig instance.
        """
        self.console = config.console or Console()
        self.accessible_mode = config.accessible_mode
        self.layout_settings = config.layout_settings
        self.theme = config.get_resolved_theme()

    def print(self: Self, text: str, style: str | None = None) -> None:
        """Print text with optional styling.

        Args:
            text: Text to print.
            style: Optional Rich style string.
        """
        self.console.print(text, style=style)

    def success(self: Self, message: str) -> None:
        """Print a success message.

        Args:
            message: Success message text.
        """
        self._print_status_message(
            StatusMessageParams(message=message, status_type=StatusType.SUCCESS),
        )

    def info(self: Self, message: str) -> None:
        """Print an info message.

        Args:
            message: Info message text.
        """
        self._print_status_message(
            StatusMessageParams(message=message, status_type=StatusType.INFO),
        )

    def warning(self: Self, message: str) -> None:
        """Print a warning message.

        Args:
            message: Warning message text.
        """
        self._print_status_message(
            StatusMessageParams(message=message, status_type=StatusType.WARNING),
        )

    def error(self: Self, message: str) -> None:
        """Print an error message.

        Args:
            message: Error message text.
        """
        self._print_status_message(
            StatusMessageParams(message=message, status_type=StatusType.ERROR),
        )

    def _print_status_message(self: Self, params: StatusMessageParams) -> None:
        """Print a status message with consistent formatting.

        Args:
            params: Status message parameters.
        """
        prefix = (
            params.status_type.accessible_icon if self.accessible_mode else params.status_type.icon
        )
        color = getattr(self.theme, params.status_type.style)
        self.console.print(f"[{color}]{prefix}[/] {escape(params.message)}")

    def muted(self: Self, text: str) -> None:
        """Print muted/dim text.

        Args:
            text: Text to print.
        """
        self.console.print(text, style=self.theme.muted)

    def heading(self: Self, text: str) -> None:
        """Print a heading.

        Args:
            text: Heading text.
        """
        self.console.print(f"\n[bold {self.theme.primary}]{escape(text)}[/]\n")

    def markdown(self: Self, content: str) -> None:
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

    def code(self: Self, code: str, language: str = "python") -> None:
        """Print syntax-highlighted code.

        Args:
            code: Code to display.
            language: Programming language for highlighting.
        """
        if not code:
            return
        syntax = Syntax(code, language, theme="monokai")
        self.console.print(syntax)

    def rule(self: Self, title: str | None = None) -> None:
        """Print a horizontal rule.

        Args:
            title: Optional title for the rule.
        """
        if title:
            self.console.rule(title=title)
        else:
            self.console.rule()

    def clear(self: Self) -> None:
        """Clear the console screen."""
        self.console.clear()

    def tool_call(self: Self, name: str, arguments: dict[str, object]) -> None:
        """Display a tool call.

        Args:
            name: Tool name.
            arguments: Tool arguments.
        """
        args_str = json.dumps(arguments, indent=2)
        # Escape backticks in tool name to prevent markdown code-fence breakout
        safe_name = name.replace("`", "\\`")
        content = f"### 🛠️ Tool Call: `{safe_name}`\n\n```json\n{args_str}\n```"
        self.markdown(content)

    def tool_result(self: Self, content: str, *, success: bool = True, error: str | None = None) -> None:  # noqa: E501
        """Display a tool result.

        Args:
            content: Result content.
            success: Whether the tool execution was successful.
            error: Optional error message if failed.
        """
        # Truncate content if too long
        if len(content) > _MAX_TOOL_RESULT_LEN:
            content = content[:_MAX_TOOL_RESULT_LEN]
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

    def table(self: Self, data: list[dict[str, object]], title: str | None = None) -> None:
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
            title=title,
            show_header=True,
            header_style=f"bold {self.theme.primary}",
            box=table_box,
        )

        # Add columns from first row keys
        for key in data[0]:
            table.add_column(str(key))

        # Add rows
        for row in data:
            table.add_row(*[str(v) for v in row.values()])

        self.console.print(table)

    def tree(self: Self, root_name: str, items: list[tuple[str, str]]) -> None:
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

    def diff(self: Self, *args: str | DiffParams, **kwargs: str) -> None:
        """Render diff between old and new content.

        Accepts either:
        - Three string arguments: old, new, filename (optional)
        - A single DiffParams object

        Args:
            *args: Either (old, new, filename) strings or a DiffParams object.
            **kwargs: Keyword arguments for backward compatibility.
        """
        params = self._parse_diff_args(*args, **kwargs)
        self._render_diff(params)

    def _parse_diff_args(self: Self, *args: str | DiffParams, **kwargs: str) -> DiffParams:
        """Parse diff arguments into DiffParams.

        Handles both primitive parameters and DiffParams object.

        Args:
            *args: Either (old, new, filename) strings or a DiffParams object.
            **kwargs: Keyword arguments for backward compatibility.

        Returns:
            DiffParams object.

        Raises:
            TypeError: If arguments are invalid.
        """
        if len(args) == 1 and isinstance(args[0], DiffParams):
            return args[0]
        if _MIN_DIFF_ARGS <= len(args) <= _MAX_DIFF_ARGS:
            old = str(args[0])
            new = str(args[1])
            filename = str(args[2]) if len(args) > _MIN_DIFF_ARGS else kwargs.get("filename", "")
            return DiffParams(old, new, filename)
        error_msg = (
            "diff() takes either a DiffParams object or 2-3 string arguments "
            "(old, new, filename)"
        )
        raise TypeError(error_msg)

    def _render_diff(self: Self, params: DiffParams) -> None:
        """Render diff using DiffParams object.

        Args:
            params: Diff parameters.
        """
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

    def tool_summary(self: Self, name: str, duration: float | None = None) -> None:
        """Display a summary of tool execution.

        Args:
            name: Tool name.
            duration: Execution duration in seconds.
        """
        msg = f"Executed {name}"
        if duration is not None:
            msg += f" ({duration:.2f}s)"
        self.console.print(msg)

    def print_agent_content(self: Self, content: str) -> None:
        """Display content from the agent.

        Args:
            content: Content string.
        """
        self.console.print(content, end="")

    def agent_content(self: Self, content: str) -> None:
        """Display content from the agent (alias for print_agent_content).

        Args:
            content: Content string.
        """
        self.print_agent_content(content)

    def thinking(self: Self, content: str) -> None:
        """Display thinking process.

        Args:
            content: Thinking content.
        """
        # Escape content to prevent rich markup interpretation
        # Note: We should eventually render markdown properly, but for now
        # escape to show raw content including markdown symbols
        self.console.print(escape(content), style=self.theme.muted, end="")

    async def confirm_tool_execution(self: Self, message: str) -> bool:
        """Ask user for confirmation.

        Args:
            message: Confirmation message.

        Returns:
            True if confirmed.
        """
        return await anyio.to_thread.run_sync(lambda: Confirm.ask(message, console=self.console))


class AsyncOutputRenderer:
    """Async wrapper for OutputRenderer."""

    def __init__(self: Self, renderer: OutputRenderer) -> None:
        """Initialize the async renderer.

        Args:
            renderer: Sync OutputRenderer instance.
        """
        self.renderer = renderer
        self._async_methods: dict[str, Callable[..., Any]] = {}

    def __getattr__(self: Self, name: str) -> Callable[..., Any]:
        """Dynamically create async wrappers for OutputRenderer methods.

        Args:
            name: Method name to look up.

        Returns:
            Async wrapper function for the method.

        Raises:
            AttributeError: If the method doesn't exist on OutputRenderer.
        """
        self._validate_method_name(name)

        # Return cached wrapper if available
        if name in self._async_methods:
            return self._async_methods[name]

        # Create and cache wrapper
        wrapper = self._create_async_wrapper(name)
        self._async_methods[name] = wrapper
        return wrapper

    def _validate_method_name(self: Self, name: str) -> None:
        """Validate that method name is valid for async wrapping.

        Args:
            name: Method name to validate.

        Raises:
            AttributeError: If method is invalid.
        """
        if not hasattr(self.renderer, name):
            error_msg = f"'{type(self).__name__}' object has no attribute '{name}'"
            raise AttributeError(error_msg)

        if name.startswith("_"):
            error_msg = f"'{type(self).__name__}' object has no attribute '{name}'"
            raise AttributeError(error_msg)

    def _create_async_wrapper(self: Self, name: str) -> Callable[..., Any]:
        """Create an async wrapper for a sync method.

        Args:
            name: Method name to wrap.

        Returns:
            Async wrapper function.
        """
        sync_method = getattr(self.renderer, name)

        # Special handling for diff method
        if name == "diff":
            return self._create_async_diff_wrapper()

        # Generic async wrapper for other methods
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            def sync_wrapper() -> Any:
                return sync_method(*args, **kwargs)

            return await anyio.to_thread.run_sync(sync_wrapper)

        return async_wrapper

    def _create_async_diff_wrapper(self: Self) -> Callable[..., Any]:
        """Create async wrapper for diff method.

        Returns:
            Async diff wrapper function.
        """

        async def async_diff(*args: str | DiffParams, **kwargs: str) -> None:
            """Async version of diff method.

            Accepts either:
            - Three string arguments: old, new, filename (optional)
            - A single DiffParams object

            Args:
                *args: Either (old, new, filename) strings or a DiffParams object.
                **kwargs: Keyword arguments for backward compatibility.
            """
            params = self.renderer._parse_diff_args(*args, **kwargs)  # noqa: SLF001
            await anyio.to_thread.run_sync(self.renderer._render_diff, params)  # noqa: SLF001

        return async_diff
