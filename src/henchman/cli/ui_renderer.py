"""UI Renderer for REPL-specific user interface elements.

This module provides a UIRenderer class that encapsulates all UI rendering logic
for the REPL, including welcome/goodbye messages, status updates, tool confirmations,
and error messages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.status import Status

from henchman.cli.console import OutputRenderer
from henchman.core.session import Session


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
    ) -> None:
        """Initialize the UI renderer.

        Args:
            console: Rich Console to use, or creates a new one.
            renderer: OutputRenderer to wrap, or creates a new one.
        """
        self.console = console or Console()
        self.renderer = renderer or OutputRenderer(console=self.console)

    def print_welcome(self) -> None:
        """Print welcome message."""
        self.console.print("[bold blue]Henchman-AI[/] - /help for commands, /quit to exit\n")

    def print_goodbye(self) -> None:
        """Print goodbye message."""
        self.console.print("[dim]Goodbye![/]")

    def get_rich_status_message(self, session: Session | None, agent: Any | None, rag_system: Any | None = None) -> str:
        """Get rich status message for persistent display.

        Args:
            session: Current session object.
            agent: Current agent object (could be orchestrator.tech_lead).
            rag_system: RAG system object for indexing status.

        Returns:
            Formatted status message string.
        """
        from henchman.utils.tokens import TokenCounter

        parts = []

        # Plan Mode
        plan_mode = session.plan_mode if session else False
        parts.append("[yellow]PLAN[/]" if plan_mode else "[blue]CHAT[/]")

        # Tokens
        if agent and hasattr(agent, 'get_messages_for_api'):
            try:
                msgs = agent.get_messages_for_api()
                tokens = TokenCounter.count_messages(msgs)
                parts.append(f"Tokens: ~[cyan]{tokens}[/]")
            except Exception:
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

    def print_newline(self) -> None:
        """Print a newline."""
        self.console.print()

    def print_agent_content(self, content: str) -> None:
        """Print agent content without newline.

        Args:
            content: Content to print.
        """
        self.console.print(content, end="")

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

    def tool_result(self, content: str, success: bool = True, error: str | None = None) -> None:
        """Display a tool result."""
        self.renderer.tool_result(content, success, error)

    def tool_summary(self, name: str, duration: float | None = None) -> None:
        """Display a summary of tool execution."""
        self.renderer.tool_summary(name, duration)

    def agent_content(self, content: str) -> None:
        """Display content from the agent."""
        self.renderer.agent_content(content)

    def thinking(self, content: str) -> None:
        """Display thinking process."""
        self.renderer.thinking(content)

    async def confirm_tool_execution(self, message: str) -> bool:
        """Ask user for confirmation.

        Args:
            message: Confirmation message.

        Returns:
            True if confirmed.
        """
        return await self.renderer.confirm_tool_execution(message)
