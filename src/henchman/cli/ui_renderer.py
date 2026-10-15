"""UI Renderer for REPL-specific user interface elements.

This module provides a UIRenderer class that encapsulates all UI rendering logic
for the REPL, including welcome/goodbye messages, status updates, tool confirmations,
and error messages.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from henchman.cli.console import OutputRenderer

if TYPE_CHECKING:
    from collections.abc import Generator

    from rich.status import Status


class ProgressManager:
    """Manage progress indicators for long operations.

    This class handles creating and updating progress bars using Rich's Progress
    component. It supports tracking multiple tasks by ID.
    """

    def __init__(self: ProgressManager, console: Console) -> None:
        """Initialize the progress manager.

        Args:
            console: Rich console to render progress bars.

        """
        self.console = console
        self.tasks: dict[str, tuple[Progress, TaskID]] = {}

    def start_task(
        self: ProgressManager,
        task_id: str,
        description: str,
        total: int = 100,
    ) -> Progress:
        """Start a new progress task.

        Args:
            task_id: Unique identifier for the task.
            description: Description to show next to the progress bar.
            total: Total steps for the task.

        Returns:
            The created Progress instance.

        """
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=True,
        )
        task = progress.add_task(description, total=total)
        progress.start()
        self.tasks[task_id] = (progress, task)
        return progress

    def update_task(
        self: ProgressManager,
        task_id: str,
        advance: int = 1,
        description: str | None = None,
    ) -> None:
        """Update progress for a task.

        Args:
            task_id: Task identifier.
            advance: Number of steps to advance.
            description: Optional new description.

        Returns:
            None

        """
        if task_id in self.tasks:
            progress, task = self.tasks[task_id]
            kwargs: dict[str, object] = {"advance": advance}
            if description:
                kwargs["description"] = description
            progress.update(task, **kwargs)  # type: ignore[arg-type]

    def complete_task(self: ProgressManager, task_id: str) -> None:
        """Complete and remove a task.

        Args:
            task_id: Task identifier.

        Returns:
            None

        """
        if task_id in self.tasks:
            progress, _task = self.tasks[task_id]
            progress.stop()
            del self.tasks[task_id]


class UIRenderer:
    """Renders REPL-specific UI elements.

    This class wraps OutputRenderer and adds REPL-specific UI methods
    for welcome/goodbye messages, status updates, and other REPL-specific
    rendering concerns.

    Renderer and progress-manager methods are available transparently via
    __getattr__ delegation — no explicit one-liner wrappers needed.

    Attributes:
        renderer: Underlying OutputRenderer for basic console operations.
        console: Rich Console instance.

    """

    def __init__(
        self: UIRenderer,
        console: Console | None = None,
        renderer: OutputRenderer | None = None,
        *,
        accessible_mode: bool = False,
        style_overrides: dict[str, str] | None = None,
        layout_settings: object | None = None,
    ) -> None:
        """Initialize the UI renderer.

        Args:
            console: Rich Console to use, or creates a new one.
            renderer: OutputRenderer to wrap, or creates a new one.
            accessible_mode: Whether to enable high-accessibility mode.
            style_overrides: Optional style overrides.
            layout_settings: Optional layout settings.

        """
        self.console = console or Console()
        self.renderer = renderer or OutputRenderer(
            console=self.console,
            accessible_mode=accessible_mode,
            style_overrides=style_overrides,
            layout_settings=layout_settings,
        )
        self.progress_manager = ProgressManager(self.console)
        self._thinking_status: Status | None = None
        self._is_thinking: bool = False

    def __getattr__(self: UIRenderer, name: str) -> Any:
        """Delegate unknown attribute access to renderer then progress_manager.

        Transparently proxies all renderer and progress manager methods so that
        UIRenderer does not need to redeclare each single-line delegate.

        Args:
            name: Attribute name to look up.

        Returns:
            The attribute from the renderer or progress manager.

        Raises:
            AttributeError: If the attribute is not found on either delegate.

        """
        for attr_name in ("renderer", "progress_manager"):
            try:
                obj = object.__getattribute__(self, attr_name)
            except AttributeError:
                continue
            try:
                return getattr(obj, name)
            except AttributeError:
                continue
        msg = f"'{type(self).__name__}' object has no attribute '{name}'"
        raise AttributeError(msg)

    async def confirm_tool_execution(self: UIRenderer, message: str) -> bool:
        """Forward tool confirmation to the underlying output renderer."""
        return await self.renderer.confirm_tool_execution(message)

    def print_welcome(self: UIRenderer) -> None:
        """Print welcome message.

        Returns:
            None

        """
        self.console.print(
            "[bold blue]Henchman-AI[/] - /help for commands, /quit to exit\n",
        )

    def print_goodbye(self: UIRenderer) -> None:
        """Print goodbye message.

        Returns:
            None

        """
        self.console.print("[dim]Goodbye![/]")

    def create_status(self: UIRenderer, message: str, spinner: str = "dots") -> Status:
        """Create a rich status context manager.

        Args:
            message: Status message text.
            spinner: Spinner style.

        Returns:
            Rich Status context manager.

        """
        return self.console.status(message, spinner=spinner)

    def start_thinking(
        self: UIRenderer,
        message: str | None = None,
        spinner: str = "dots",
    ) -> None:
        """Start a thinking indicator.

        Args:
            message: Optional custom thinking message.
            spinner: Spinner style (e.g., "dots", "line", "circle").

        Returns:
            None

        """
        if self._is_thinking:
            self.stop_thinking()

        thinking_msg = "[dim]Thinking…[/]"
        if message:
            thinking_msg += f" {escape(message)}"

        self._thinking_status = self.console.status(thinking_msg, spinner=spinner)
        try:
            self._thinking_status.__enter__()
            self._is_thinking = True
        except Exception:
            self._thinking_status = None
            self._is_thinking = False

    def stop_thinking(self: UIRenderer) -> None:
        """Stop the current thinking indicator.

        Returns:
            None

        """
        if self._thinking_status and self._is_thinking:
            import contextlib

            with contextlib.suppress(Exception):
                self._thinking_status.__exit__(None, None, None)

        self._thinking_status = None
        self._is_thinking = False

    @property
    def is_thinking(self: UIRenderer) -> bool:
        """Check if thinking indicator is active.

        Returns:
            True if thinking indicator is active.

        """
        return self._is_thinking

    @contextmanager
    def thinking_context(
        self: UIRenderer,
        message: str | None = None,
        spinner: str = "dots",
    ) -> Generator[None, None, None]:
        """Context manager for thinking indicator.

        Args:
            message: Optional custom thinking message.
            spinner: Spinner style (e.g., "dots", "line", "circle").

        Yields:
            The context for thinking indicator.

        """
        try:
            self.start_thinking(message, spinner=spinner)
            yield
        finally:
            self.stop_thinking()

    def print_newline(self: UIRenderer) -> None:
        """Print a newline.

        Returns:
            None

        """
        self.console.print()

    def show_thinking(self: UIRenderer, content: str) -> None:
        """Display thinking process content (alias for clarity).

        Args:
            content: Thinking content to display.

        Returns:
            None

        """
        self.thinking(content)
