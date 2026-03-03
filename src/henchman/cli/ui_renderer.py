"""UI Renderer for REPL-specific user interface elements.

This module provides a UIRenderer class that encapsulates all UI rendering logic
for the REPL, including welcome/goodbye messages, status updates, tool confirmations,
and error messages.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from rich.console import Console
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

    from henchman.core.session import Session


class ProgressManager:
    """Manage progress indicators for long operations.

    This class handles creating and updating progress bars using Rich's Progress
    component. It supports tracking multiple tasks by ID.
    """

    def __init__(self, console: Console):
        """Initialize the progress manager.

        Args:
            console: Rich console to render progress bars.
        """
        self.console = console
        self.tasks: dict[str, tuple[Progress, TaskID]] = {}

    def start_task(self, task_id: str, description: str, total: int = 100) -> Progress:
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

    def update_task(self, task_id: str, advance: int = 1, description: str | None = None) -> None:
        """Update progress for a task.

        Args:
            task_id: Task identifier.
            advance: Number of steps to advance.
            description: Optional new description.
        """
        if task_id in self.tasks:
            progress, task = self.tasks[task_id]
            kwargs: dict[str, object] = {"advance": advance}
            if description:
                kwargs["description"] = description
            progress.update(task, **kwargs)  # type: ignore[arg-type]

    def complete_task(self, task_id: str) -> None:
        """Complete and remove a task.

        Args:
            task_id: Task identifier.
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

    Attributes:
        renderer: Underlying OutputRenderer for basic console operations.
        console: Rich Console instance.
    """

    def __init__(
        self,
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

    def print_welcome(self) -> None:
        """Print welcome message."""
        self.console.print("[bold blue]Henchman-AI[/] - /help for commands, /quit to exit\n")

    def print_goodbye(self) -> None:
        """Print goodbye message."""
        self.console.print("[dim]Goodbye![/]")

    def get_rich_status_message(
        self,
        session: Session | None,
        agent: Any | None,
        rag_system: Any | None = None,
    ) -> str:
        """Get rich status message for persistent display.

        Args:
            session: Current session object.
            agent: Current agent object (could be orchestrator.tech_lead).
            rag_system: RAG system object for indexing status.

        Returns:
            Formatted status message string.
        """
        from henchman.utils.tokens import TokenCounter  # noqa: PLC0415

        parts = []

        # Plan Mode
        plan_mode = session.plan_mode if session else False
        parts.append("[yellow]PLAN[/]" if plan_mode else "[blue]CHAT[/]")

        # Tokens
        if agent and hasattr(agent, "get_messages_for_api"):
            try:
                msgs = agent.get_messages_for_api()
                tokens = TokenCounter.count_messages(msgs)
                parts.append(f"Tokens: ~[cyan]{tokens}[/]")
            except Exception:  # noqa: BLE001
                pass

        # RAG Status
        if rag_system and getattr(rag_system, "is_indexing", False):
            parts.append("[cyan]RAG: Indexing...[/]")

        return " | ".join(parts)

    def create_status(self, message: str, spinner: str = "dots") -> Status:
        """Create a rich status context manager.

        Args:
            message: Status message text.
            spinner: Spinner style.

        Returns:
            Rich Status context manager.
        """
        return self.console.status(message, spinner=spinner)

    def start_thinking(self, message: str | None = None, spinner: str = "dots") -> None:
        """Start a thinking indicator.

        Args:
            message: Optional custom thinking message.
            spinner: Spinner style (e.g., "dots", "line", "circle").
        """
        if self._is_thinking:
            self.stop_thinking()

        thinking_msg = "[dim]Thinking...[/]"
        if message:
            thinking_msg += f" {message}"

        self._thinking_status = self.console.status(thinking_msg, spinner=spinner)
        try:
            self._thinking_status.__enter__()
            self._is_thinking = True
        except Exception:  # noqa: BLE001
            self._thinking_status = None
            self._is_thinking = False

    def stop_thinking(self) -> None:
        """Stop the current thinking indicator."""
        if self._thinking_status and self._is_thinking:
            import contextlib  # noqa: PLC0415
            with contextlib.suppress(Exception):
                self._thinking_status.__exit__(None, None, None)

        self._thinking_status = None
        self._is_thinking = False

    @property
    def is_thinking(self) -> bool:
        """Check if thinking indicator is active.

        Returns:
            True if thinking indicator is active.
        """
        return self._is_thinking

    @contextmanager
    def thinking_context(self, message: str | None = None, spinner: str = "dots") -> Generator[None, None, None]:  # noqa: E501
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

    def print_newline(self) -> None:
        """Print a newline."""
        self.console.print()

    def print_agent_content(self, content: str) -> None:
        """Print agent content without newline.

        Args:
            content: Content to print.
        """
        self.renderer.print_agent_content(content)

    def agent_content(self, content: str) -> None:
        """Display content from the agent.

        Args:
            content: Content string.
        """
        self.renderer.agent_content(content)

    # Delegate methods to underlying renderer
    def success(self, message: str) -> None:
        """Print a success message."""
        self.renderer.success(message)

    def info(self, message: str) -> None:
        """Print an info message."""
        self.renderer.info(message)

    def warning(self, message: str) -> None:
        """Print a warning message."""
        self.renderer.warning(message)

    def error(self, message: str) -> None:
        """Print an error message."""
        self.renderer.error(message)

    def muted(self, text: str) -> None:
        """Print muted/dim text."""
        self.renderer.muted(text)

    def heading(self, text: str) -> None:
        """Print a heading."""
        self.renderer.heading(text)

    def markdown(self, content: str) -> None:
        """Render markdown content."""
        self.renderer.markdown(content)

    def code(self, code: str, language: str = "python") -> None:
        """Print syntax-highlighted code."""
        self.renderer.code(code, language)

    def rule(self, title: str | None = None) -> None:
        """Print a horizontal rule."""
        self.renderer.rule(title)

    def clear(self) -> None:
        """Clear the console screen."""
        self.renderer.clear()

    def tool_call(self, name: str, arguments: dict[str, object]) -> None:
        """Display a tool call."""
        self.renderer.tool_call(name, arguments)

    def tool_result(self, content: str, *, success: bool = True, error: str | None = None) -> None:
        """Display a tool result."""
        self.renderer.tool_result(content, success=success, error=error)

    def tool_summary(self, name: str, duration: float | None = None) -> None:
        """Display a summary of tool execution."""
        self.renderer.tool_summary(name, duration)



    def thinking(self, content: str) -> None:
        """Display thinking process content.

        Args:
            content: Thinking content to display.
        """
        self.renderer.thinking(content)

    # Alias for clarity
    def show_thinking(self, content: str) -> None:
        """Display thinking process content.

        Args:
            content: Thinking content to display.
        """
        self.thinking(content)

    async def confirm_tool_execution(self, message: str) -> bool:
        """Ask user for confirmation.

        Args:
            message: Confirmation message.

        Returns:
            True if confirmed.
        """
        return await self.renderer.confirm_tool_execution(message)

    def start_task(self, task_id: str, description: str, total: int = 100) -> Progress:
        """Start a new progress task.

        Args:
            task_id: Unique identifier for the task.
            description: Description to show next to the progress bar.
            total: Total steps for the task.

        Returns:
            The created Progress instance.
        """
        return self.progress_manager.start_task(task_id, description, total)

    def update_task(self, task_id: str, advance: int = 1, description: str | None = None) -> None:
        """Update progress for a task.

        Args:
            task_id: Task identifier.
            advance: Number of steps to advance.
            description: Optional new description.
        """
        self.progress_manager.update_task(task_id, advance, description)

    def complete_task(self, task_id: str) -> None:
        """Complete and remove a task.

        Args:
            task_id: Task identifier.
        """
        self.progress_manager.complete_task(task_id)
