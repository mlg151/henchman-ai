"""REPL (Read-Eval-Print Loop) for interactive mode.

This module provides the main interactive loop for the CLI.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.command_processor import CommandProcessor
from henchman.cli.input_handler import InputHandler
from henchman.cli.output_handler import OutputHandler
from henchman.cli.plugins import PluginManager
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.tool_manager import ToolManager
from henchman.cli.ui_renderer import UIRenderer
from henchman.core.eventbus import EventBus
from henchman.core.events import AgentEvent, EventType
from henchman.core.session import Session
from henchman.mcp.manager import McpManager
from henchman.providers.base import ModelProvider, ToolCall
from henchman.tools.base import ConfirmationRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.config.schema import Settings
    from henchman.core.agent import Agent
    from henchman.core.events import AgentEvent


@dataclass
class ReplConfig:
    """Configuration for the REPL.

    Attributes:
        prompt: The prompt string to display.
        system_prompt: System prompt for the agent.
        auto_save: Whether to auto-save sessions on exit.
        history_file: Path to history file.
        base_tool_iterations: Base limit for tool iterations per turn.
        max_tool_calls_per_turn: Maximum tool calls allowed per turn.
        auto_approve_tools: Auto-approve all tool executions (non-interactive mode).
        agent_role: Target a specific agent role for all inputs.
    """

    prompt: str = "❯ "
    system_prompt: str = ""
    auto_save: bool = True
    history_file: Path | None = None
    base_tool_iterations: int = 25
    max_tool_calls_per_turn: int = 100
    auto_approve_tools: bool = False
    agent_role: str | None = None


class Repl:
    """Interactive REPL for the CLI.

    The Repl class orchestrates the main interaction loop, connecting
    the Agent, InputHandler, OutputRenderer, and command system.

    Example:
        >>> provider = DeepSeekProvider(api_key="...")
        >>> repl = Repl(provider=provider)
        >>> await repl.run()
    """

    def __init__(
        self,
        provider: ModelProvider,
        console: Console | None = None,
        config: ReplConfig | None = None,
        settings: Settings | None = None,
        environment_context: str | None = None,
        renderer: UIRenderer | None = None,
    ) -> None:
        """Initialize the REPL.

        Args:
            provider: Model provider for LLM interactions.
            console: Rich console for output.
            config: REPL configuration.
            settings: Application settings for context limits, etc.
            environment_context: Pre-formatted environment block for agents.
            renderer: Custom UI renderer to use.
        """
        self.provider = provider
        self.console = console or Console()
        self.config = config or ReplConfig()
        self.settings = settings

        accessible_mode = settings.ui.accessible_mode if settings and settings.ui else False
        style_overrides = settings.ui.style_overrides if settings and settings.ui else None
        layout_settings = getattr(settings.ui, "layout", None) if settings and settings.ui else None
        self.renderer = renderer or UIRenderer(
            console=self.console,
            accessible_mode=accessible_mode,
            style_overrides=style_overrides,
            layout_settings=layout_settings,
        )

        # Initialize tool manager
        self.tool_manager = ToolManager(settings=settings)
        self.tool_manager.set_auto_approve(self.config.auto_approve_tools)
        self.tool_manager.register_builtin_tools()
        self.tool_registry = self.tool_manager.registry  # Backwards compatibility

        # Initialize MCP manager if servers are configured
        self.mcp_manager: McpManager | None = None
        if settings and settings.mcp_servers:
            mcp_logging = settings.ui.mcp_logging if settings.ui else False
            self.mcp_manager = McpManager.create_from_settings(settings, mcp_logging)

        # Initialize Plugin Manager
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_plugins_from_directory(Path.home() / ".henchman" / "plugins")
        # Also load from workspace plugins
        self.plugin_manager.load_plugins_from_directory(Path.cwd() / ".henchman" / "plugins")

        # Initialize EventBus
        self.event_bus = EventBus()

        # Initialize Orchestrator
        self.orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=self.tool_registry,
            event_bus=self.event_bus,
            settings=settings,
            system_prompt=self.config.system_prompt,
            environment_context=environment_context,
        )

        # Reference Tech Lead as self.agent for backwards compatibility
        self.agent = self.orchestrator.tech_lead

        self.running = False

        # Session management
        self.session_manager = ReplSessionManager(auto_save=self.config.auto_save)

        # RAG system (set externally by app.py)
        self.rag_system: object | None = None
        self.current_monitor: object | None = None

        # Initialize OutputHandler
        self.output_handler = OutputHandler(
            renderer=self.renderer,
            tool_manager=self.tool_manager,
            session_manager=self.session_manager,
            provider=self.provider,
            settings=self.settings,
            rag_system=self.rag_system,
            mcp_manager=self.mcp_manager,
        )

        # Initialize CommandProcessor
        self.command_processor = CommandProcessor(
            output_handler=self.output_handler,
            tool_manager=self.tool_manager,
            session_manager=self.session_manager,
            provider=self.provider,
            mcp_manager=self.mcp_manager,
        )

        # Initialize ToolExecutor
        self.tool_executor = ToolExecutor(
            output_handler=self.output_handler,
            tool_manager=self.tool_manager,
            provider=self.provider,
            base_tool_iterations=self.config.base_tool_iterations,
            max_tool_calls_per_turn=self.config.max_tool_calls_per_turn,
        )
        # Set confirmation handler on tool manager
        self.tool_manager.set_confirmation_handler(self.tool_executor.handle_confirmation)

        # Initialize InputHandler
        history_file = self.config.history_file or Path.home() / ".henchman_history"

        keybindings = settings.ui.keybindings if settings and settings.ui else None

        self.input_handler = InputHandler(
            config=self.config,
            renderer=self.renderer,
            history_file=history_file,
            keybindings=keybindings,
            tool_registry=self.tool_registry,
        )
        # Initialize prompt session in InputHandler
        self.input_handler.initialize_prompt_session(
            bottom_toolbar=lambda: self.output_handler.get_toolbar_status(self.agent)
        )

    def set_session(self, session: Session) -> None:
        """Set the current session and sync with agent history.

        Args:
            session: The session to activate.
        """
        self.session_manager.set_session(session, self.orchestrator)

    async def _handle_confirmation(self, request: ConfirmationRequest) -> bool:
        """Handle a tool confirmation request from the registry.

        Args:
            request: The confirmation request data.

        Returns:
            True if approved, False otherwise.
        """
        return await self.tool_executor.handle_confirmation(request)

    async def initialize_mcp(self) -> None:
        """Initialize MCP servers and register tools.

        This method can be called separately for headless mode.
        """
        if (
            self.mcp_manager and not self.mcp_manager.clients
        ):  # Only connect if not already connected
            try:
                await self.mcp_manager.connect_all()
                # Register MCP tools with the tool registry
                for tool in self.mcp_manager.get_all_tools():
                    self.tool_registry.register(tool)
                if (
                    self.mcp_manager.get_all_tools()
                    and self.settings
                    and self.settings.ui.mcp_logging
                ):
                    self.renderer.success(
                        f"Connected to {len(self.mcp_manager.clients)} MCP server(s) with {len(self.mcp_manager.get_all_tools())} tools"
                    )
            except Exception as e:
                # Always show errors, regardless of logging setting
                self.renderer.error(f"Failed to connect to MCP servers: {e}")

    async def run(self) -> None:
        """Run the main REPL loop.

        This method runs until the user exits with /quit, Ctrl+C, or Ctrl+D.
        """
        self.running = True
        self.output_handler.print_welcome()
        await self.initialize_mcp()

        # Start background indexing if RAG is available
        self.output_handler.start_background_indexing()

        try:
            while self.running:
                try:
                    user_input = await self._get_input()
                    should_continue = await self.process_input(user_input)
                    if not should_continue:
                        break
                except KeyboardInterrupt:
                    self.running = False
                    break
                except EOFError:
                    self.renderer.print_newline()
                    break
        finally:
            self.running = False
            if self.mcp_manager:
                await self.mcp_manager.disconnect_all()
            self._auto_save_session()
            self.output_handler.print_goodbye()

    def _auto_save_session(self) -> None:
        """Auto-save the session if enabled and session has content."""
        self.session_manager.auto_save_session()

    async def _get_input(self) -> str:
        """Get input from the user.

        Returns:
            User input string.

        Raises:
            KeyboardInterrupt: If user presses Ctrl+C.
            EOFError: If user presses Ctrl+D.
        """
        return await self.input_handler.get_input()

    async def process_input(self, user_input: str) -> bool:
        """Process a single user input.

        Args:
            user_input: The user's input string.

        Returns:
            True to continue running, False to exit.
        """
        # Use InputHandler to process input
        processed_input, is_command, should_continue = await self.input_handler.process_input(
            user_input
        )

        if not should_continue:
            return False

        # Skip empty input (already processed by InputHandler, but double-check)
        if not processed_input:
            return True

        if is_command:
            # Handle slash commands
            return await self.command_processor.handle_command(processed_input, self.agent, self)

        # Run through agent with expanded input
        await self._run_agent(processed_input)
        return True

    async def _run_agent(self, user_input: str) -> None:
        """Run the agent with user input.

        Args:
            user_input: The processed user input.
        """
        self.session_manager.record_user_message(user_input)
        assistant_content: list[str] = []
        status_msg = self.output_handler.get_rich_status_message(self.agent)
        await self._run_agent_with_monitor(
            self.orchestrator.run(user_input), self.agent, assistant_content, status_msg
        )

    async def _run_agent_direct(self, role: str, user_input: str) -> None:
        """Run a specific agent directly.

        Args:
            role: Agent role to target.
            user_input: The user's input.
        """
        self.session_manager.record_user_message(f"[@{role}] {user_input}")
        assistant_content: list[str] = []
        status_msg = f"[bold cyan]@{role}[/] thinking..."
        agent = self.orchestrator.pool.get_agent(role)
        await self._run_agent_with_monitor(
            self.orchestrator.run_direct(role, user_input), agent, assistant_content, status_msg
        )

    async def _run_agent_with_monitor(
        self,
        event_stream: AsyncIterator[AgentEvent],
        agent: Agent,
        assistant_content: list[str],
        status_msg: str,
    ) -> None:
        """Run agent with monitor setup and cancellation handling.

        Args:
            event_stream: Agent event stream.
            agent: The agent to run.
            assistant_content: List to collect assistant content.
            status_msg: Status message to display.
        """
        from henchman.cli.input import KeyMonitor

        monitor = KeyMonitor()
        self.current_monitor = monitor
        monitor_task = asyncio.create_task(monitor.monitor())

        try:
            # Print status message without spinner
            if status_msg:
                self.renderer.info(status_msg)

            agent_task = asyncio.create_task(
                self.tool_executor.process_agent_stream(
                    event_stream,
                    agent,
                    assistant_content,
                    None,  # No status object
                )
            )

            # Wait for agent task or monitor cancellation
            while not agent_task.done():
                if monitor.exit_requested:
                    self.renderer.warning("\n[Exit requested by Ctrl+C]")
                    self.running = False
                    agent_task.cancel()
                    break
                if monitor.stop_requested:
                    self.renderer.warning("\n[Interrupted by Esc]")
                    agent_task.cancel()
                    break
                await asyncio.sleep(0.1)

            # Await agent task (handles cancellation)
            with contextlib.suppress(asyncio.CancelledError):
                await agent_task

        except Exception as e:
            self.renderer.error(f"Error: {e}")
        finally:
            # Signal monitor to stop
            if hasattr(monitor, "_stop_event"):
                monitor._stop_event.set()

            # Wait for monitor task to complete with timeout
            try:
                await asyncio.wait_for(monitor_task, timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                # If monitor task doesn't complete quickly, cancel it
                monitor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await monitor_task

    async def _handle_agent_event(
        self, event: AgentEvent, content_collector: list[str] | None = None
    ) -> None:
        """Handle an event from the agent.

        DEPRECATED: Use ToolExecutor.process_agent_stream instead.
        This method is kept for backwards compatibility with tests.
        """
        if event.type == EventType.ERROR:
            self.renderer.error(str(event.data))
        elif event.type == EventType.CONTENT and content_collector is not None and event.data:
            content_collector.append(event.data)

    async def _handle_tool_call(self, tool_call: ToolCall) -> None:
        """Handle a single tool call from the agent.

        DEPRECATED: Use ToolExecutor.execute_tool_calls for proper batched handling.
        This method is kept for backwards compatibility with tests.

        Args:
            tool_call: The tool call to execute.
        """
        # Convert single tool call to list for execute_tool_calls
        await self.tool_executor.execute_tool_calls([tool_call], self.agent)
