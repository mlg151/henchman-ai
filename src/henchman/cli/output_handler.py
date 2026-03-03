"""Output handler for REPL.

This module handles console output, event streaming, and status updates.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from henchman.cli.session_manager import ReplSessionManager
    from henchman.cli.tool_manager import ToolManager
    from henchman.cli.ui_renderer import UIRenderer
    from henchman.core.agent import Agent
    from henchman.mcp.manager import McpManager
    from henchman.providers.base import ModelProvider


try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


class OutputHandler:
    """Handles output and event streaming for the REPL.

    Responsibilities:
    - Manage console output
    - Handle event streaming
    - Update status displays
    - Show turn status
    """

    def __init__(  # noqa: PLR0913
        self: Self,
        renderer: UIRenderer,
        tool_manager: ToolManager,
        session_manager: ReplSessionManager,
        provider: ModelProvider,
        settings: object | None = None,
        rag_system: object | None = None,
        mcp_manager: McpManager | None = None,
    ) -> None:
        """Initialize the output handler.

        Args:
            renderer: UI renderer for output.
            tool_manager: Tool manager for tool information.
            session_manager: Session manager for session information.
            provider: Model provider for model information.
            settings: Application settings.
            rag_system: RAG system for status information.
            mcp_manager: MCP manager for MCP connection status.
        """
        self.renderer = renderer
        self.tool_manager = tool_manager
        self.session_manager = session_manager
        self.provider = provider
        self.settings = settings
        self.rag_system = rag_system
        self.mcp_manager = mcp_manager

    def __getattr__(self: Self, name: str) -> Any:
        """Delegate unknown attribute access to the underlying renderer.

        Transparently proxies all renderer methods so that OutputHandler does
        not need to redeclare each single-line delegate.

        Args:
            name: Attribute name to look up.

        Returns:
            The attribute from the renderer.

        Raises:
            AttributeError: If neither OutputHandler nor its renderer has the attribute.
        """
        try:
            renderer = object.__getattribute__(self, "renderer")
            return getattr(renderer, name)
        except AttributeError:
            pass
        msg = f"'{type(self).__name__}' object has no attribute '{name}'"
        raise AttributeError(msg)

    def get_toolbar_status(
        self: Self, agent: Agent | None = None,
    ) -> list[tuple[str, str]]:
        """Get status bar content.

        Args:
            agent: The agent to get token information from. Required for token counting.

        Returns:
            List of (style, text) tuples for status bar.
        """
        status: list[tuple[str, str]] = []

        self._add_plan_mode_status(status)
        self._add_provider_status(status)
        self._add_token_status(status, agent)
        self._add_tool_status(status)
        self._add_mcp_status(status)
        self._add_rag_status(status)

        return status

    def _add_plan_mode_status(self: Self, status: list[tuple[str, str]]) -> None:
        """Add plan mode status to the status list.

        Args:
            status: The status list to append to.
        """
        session = self.session_manager.current
        plan_mode = session.plan_mode if session else False
        if plan_mode:
            status.append(("bg:yellow fg:black bold", " PLAN MODE "))
        else:
            status.append(("bg:blue fg:white bold", " CHAT "))

    def _add_provider_status(self: Self, status: list[tuple[str, str]]) -> None:
        """Add provider and model status to the status list.

        Args:
            status: The status list to append to.
        """
        try:
            provider_name = self.provider.__class__.__name__.replace("Provider", "")
            model_name = getattr(self.provider, "default_model", "unknown")
            status.append(("", f" {provider_name}:{model_name} "))
        except Exception:  # noqa: BLE001
            pass

    def _add_token_status(
        self: Self, status: list[tuple[str, str]], agent: Agent | None,
    ) -> None:
        """Add token usage status to the status list.

        Args:
            status: The status list to append to.
            agent: The agent to get token information from.
        """
        from henchman.utils.tokens import TokenCounter  # noqa: PLC0415

        try:
            if not agent or not hasattr(agent, "get_messages_for_api"):
                return

            msgs = agent.get_messages_for_api()
            tokens = TokenCounter.count_messages(msgs)

            max_tokens = self._get_max_tokens()
            if max_tokens > 0:
                self._add_token_percentage_status(status, tokens, max_tokens)
            else:
                status.append(("", f" Tokens: ~{tokens} "))
        except Exception:  # noqa: BLE001
            pass

    def _get_max_tokens(self: Self) -> int:
        """Get the maximum token limit from settings.

        Returns:
            Maximum token limit, or 0 if not available.
        """
        if not self.settings:
            return 0
        if not hasattr(self.settings, "context"):
            return 0
        context = getattr(self.settings, "context", None)
        if not context:
            return 0
        return getattr(context, "max_tokens", 0)

    def _add_token_percentage_status(
        self: Self,
        status: list[tuple[str, str]],
        tokens: int,
        max_tokens: int,
    ) -> None:
        """Add token percentage status with color coding.

        Args:
            status: The status list to append to.
            tokens: Current token count.
            max_tokens: Maximum token limit.
        """
        LOW_THRESHOLD = 50  # noqa: N806
        MEDIUM_THRESHOLD = 75  # noqa: N806

        percentage = (tokens / max_tokens) * 100

        if percentage < LOW_THRESHOLD:
            color = "green"
        elif percentage < MEDIUM_THRESHOLD:
            color = "yellow"
        else:
            color = "red"

        status.append((f"fg:{color}", f" Tokens: {percentage:.0f}% "))

    def _add_tool_status(self: Self, status: list[tuple[str, str]]) -> None:
        """Add tool count status to the status list.

        Args:
            status: The status list to append to.
        """
        try:
            if hasattr(self.tool_manager.registry, "list_tools"):
                tool_count = len(self.tool_manager.registry.list_tools())
                status.append(("", f" Tools: {tool_count} "))
        except Exception:  # noqa: BLE001
            pass

    def _add_mcp_status(self: Self, status: list[tuple[str, str]]) -> None:
        """Add MCP connection status to the status list.

        Args:
            status: The status list to append to.
        """
        try:
            if not self.mcp_manager or not hasattr(self.mcp_manager, "clients"):
                return

            total_clients = len(self.mcp_manager.clients)
            if total_clients == 0:
                return

            connected_clients = self._count_connected_mcp_clients()
            status.append(("", f" MCP: {connected_clients}/{total_clients} "))
        except Exception:  # noqa: BLE001
            pass

    def _count_connected_mcp_clients(self: Self) -> int:
        """Count the number of connected MCP clients.

        Returns:
            Number of connected MCP clients.
        """
        if not self.mcp_manager or not hasattr(self.mcp_manager, "clients"):
            return 0
        return sum(
            1
            for client in self.mcp_manager.clients.values()
            if hasattr(client, "is_connected") and client.is_connected
        )

    def _add_rag_status(self: Self, status: list[tuple[str, str]]) -> None:
        """Add RAG status to the status list.

        Args:
            status: The status list to append to.
        """
        if self.rag_system and getattr(self.rag_system, "is_indexing", False):
            status.append(("bg:cyan fg:black", " RAG: Indexing... "))

    def get_rich_status_message(self: Self, agent: Agent) -> str:
        """Get rich status message for persistent display.

        Args:
            agent: The agent to get status for.

        Returns:
            Status message string.
        """
        return self.renderer.get_rich_status_message(
            self.session_manager.current,
            agent,
            self.rag_system,
        )

    def show_turn_status(self: Self, agent: Agent, base_iterations: int) -> None:
        """Display current turn status.

        Args:
            agent: The agent to get turn status from.
            base_iterations: Base iteration limit.
        """
        turn = agent.turn
        status = turn.get_status_string(
            base_limit=base_iterations,
            max_tokens=getattr(agent, "max_tokens", 0),
        )

        # Color based on status
        if turn.is_spinning() or turn.is_approaching_limit(base_iterations):
            self.warning(status)
        else:
            self.muted(status)

            if self.rag_system and hasattr(self.rag_system, "index_async"):
                self._safe_create_task(self.rag_system.index_async())

    def start_background_indexing(self: Self) -> None:
        """Start background indexing if RAG is available."""
        if self.rag_system and hasattr(self.rag_system, "index_async"):
            self._safe_create_task(self.rag_system.index_async())

    @staticmethod
    def _safe_create_task(coro: Any) -> None:
        """Create an asyncio task with error logging on failure.

        Args:
            coro: Coroutine to schedule.
        """
        import logging  # noqa: PLC0415

        task = asyncio.create_task(coro)

        def _on_done(t: asyncio.Task[Any]) -> None:
            if not t.cancelled() and t.exception():
                logging.error(  # noqa: LOG015
                    "Background task failed: %s", t.exception(),
                )

        task.add_done_callback(_on_done)
