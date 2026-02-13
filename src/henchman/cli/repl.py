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
from rich.status import Status

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.commands import CommandContext, CommandRegistry, parse_command
from henchman.cli.commands.builtins import get_builtin_commands
from henchman.cli.console import OutputRenderer
from henchman.cli.input import create_session, expand_at_references, is_slash_command
from henchman.core.eventbus import EventBus
from henchman.core.events import AgentEvent, EventType
from henchman.core.session import Session, SessionManager, SessionMessage
from henchman.providers.base import Message, ModelProvider, ToolCall
from henchman.tools.base import ConfirmationRequest
from henchman.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from henchman.config.schema import Settings


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
    """

    prompt: str = "❯ "
    system_prompt: str = ""
    auto_save: bool = True
    history_file: Path | None = None
    base_tool_iterations: int = 25
    max_tool_calls_per_turn: int = 100
    auto_approve_tools: bool = False


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
    ) -> None:
        """Initialize the REPL.

        Args:
            provider: Model provider for LLM interactions.
            console: Rich console for output.
            config: REPL configuration.
            settings: Application settings for context limits, etc.
        """
        self.provider = provider
        self.console = console or Console()
        self.config = config or ReplConfig()
        self.settings = settings
        self.renderer = OutputRenderer(console=self.console)

        # Initialize tool registry with built-in tools
        self.tool_registry = ToolRegistry()
        self.tool_registry.set_confirmation_handler(self._handle_confirmation)
        self._register_builtin_tools()

        # Determine max_tokens from settings
        # Apply compaction_threshold to get the actual limit
        _max_tokens = 0
        _model_name: str | None = None
        if settings:
            context = settings.context
            if context.max_tokens > 0:
                # Apply threshold: compact when we reach threshold% of max
                _max_tokens = int(context.max_tokens * context.compaction_threshold)

        # Get model name from provider if available
        if hasattr(provider, "default_model"):
            _model_name = provider.default_model

        # Initialize EventBus
        self.event_bus = EventBus()

        # Initialize Orchestrator
        self.orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=self.tool_registry,
            event_bus=self.event_bus,
            settings=settings,
            system_prompt=self.config.system_prompt,
        )

        # Reference Tech Lead as self.agent for backwards compatibility
        self.agent = self.orchestrator.tech_lead

        # Initialize command registry
        self.command_registry = CommandRegistry()
        for cmd in get_builtin_commands():
            self.command_registry.register(cmd)

        self.running = False

        # Initialize PromptSession
        history_file = self.config.history_file or Path.home() / ".henchman_history"
        self.prompt_session = create_session(history_file, bottom_toolbar=self._get_toolbar_status)

        # Session management (can be set externally for testing)
        self.session_manager: SessionManager | None = None
        self.session: Session | None = None

        # RAG system (set externally by app.py)
        self.rag_system: object | None = None
        self.current_monitor: object | None = None

    def set_session(self, session: Session) -> None:
        """Set the current session and sync with agent history.

        Args:
            session: The session to activate.
        """
        self.session = session
        if self.session_manager:
            self.session_manager.set_current(session)

        # Restore session messages to agent history
        # Clear agent history (keeping current system prompt)
        self.agent.clear_history()

        # Convert SessionMessage objects to Message objects
        for session_msg in session.messages:
            # Convert tool_calls from dicts to ToolCall objects if present
            tool_calls = None
            if session_msg.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.get("id", ""),
                        name=tc.get("name", ""),
                        arguments=tc.get("arguments", {}),
                    )
                    for tc in session_msg.tool_calls
                ]

            msg = Message(
                role=session_msg.role,
                content=session_msg.content,
                tool_calls=tool_calls,
                tool_call_id=session_msg.tool_call_id,
            )
            self.agent.messages.append(msg)

    def _get_toolbar_status(self) -> list[tuple[str, str]]:
        """Get status bar content."""
        from henchman.utils.tokens import TokenCounter

        status = []

        # Plan Mode
        plan_mode = self.session.plan_mode if self.session else False
        if plan_mode:
            status.append(("bg:yellow fg:black bold", " PLAN MODE "))
        else:
            status.append(("bg:blue fg:white bold", " CHAT "))

        # Tokens
        try:
            msgs = self.agent.get_messages_for_api()
            tokens = TokenCounter.count_messages(msgs)
            status.append(("", f" Tokens: ~{tokens} "))
        except Exception:
            pass

        # RAG Status
        if self.rag_system and getattr(self.rag_system, "is_indexing", False):
            status.append(("bg:cyan fg:black", " RAG: Indexing... "))

        return status

    def _get_rich_status_message(self) -> str:
        """Get rich status message for persistent display."""
        from henchman.utils.tokens import TokenCounter

        parts = []

        # Plan Mode
        plan_mode = self.session.plan_mode if self.session else False
        parts.append("[yellow]PLAN[/]" if plan_mode else "[blue]CHAT[/]")

        # Tokens
        try:
            msgs = self.agent.get_messages_for_api()
            tokens = TokenCounter.count_messages(msgs)
            parts.append(f"Tokens: ~[cyan]{tokens}[/]")
        except Exception:
            pass

        # RAG Status
        if self.rag_system and getattr(self.rag_system, "is_indexing", False):
            parts.append("[cyan]RAG: Indexing...[/]")

        return " | ".join(parts)

    def _register_builtin_tools(self) -> None:
        """Register built-in tools with the registry."""
        from henchman.tools.builtins import (
            AskUserTool,
            DuckDuckGoSearchTool,
            EditFileTool,
            GlobTool,
            GrepTool,
            LsTool,
            ReadFileTool,
            ShellTool,
            WebFetchTool,
            WriteFileTool,
        )

        tools = [
            AskUserTool(),
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            LsTool(),
            GlobTool(),
            GrepTool(),
            ShellTool(
                default_timeout=(
                    self.settings.tools.shell_timeout if self.settings else 3600
                )
            ),
            WebFetchTool(),
            DuckDuckGoSearchTool(),
        ]
        for tool in tools:
            self.tool_registry.register(tool)

    async def _handle_confirmation(self, request: ConfirmationRequest) -> bool:
        """Handle a tool confirmation request from the registry.

        Args:
            request: The confirmation request data.

        Returns:
            True if approved, False otherwise.
        """
        # Auto-approve if configured
        if self.config.auto_approve_tools:
            return True

        # Formulate a clear message for the user
        import json

        msg = f"Allow tool [bold cyan]{request.tool_name}[/] to "

        if request.tool_name == "shell":
            command = (
                request.params.get("command", "unknown command")
                if request.params
                else "unknown command"
            )
            msg += f"run command: [yellow]{command}[/]"
        elif request.tool_name == "write_file":
            path = request.params.get("path", "unknown path") if request.params else "unknown path"
            msg += f"write to file: [yellow]{path}[/]"
        elif request.tool_name == "edit_file":
            path = request.params.get("path", "unknown path") if request.params else "unknown path"
            msg += f"edit file: [yellow]{path}[/]"
        else:
            msg += f"execute: {request.description}"
            if request.params:
                msg += f"\nParams: [dim]{json.dumps(request.params)}[/]"

        return await self.renderer.confirm_tool_execution(msg)

    async def run(self) -> None:
        """Run the main REPL loop.

        This method runs until the user exits with /quit, Ctrl+C, or Ctrl+D.
        """
        self.running = True
        self._print_welcome()

        # Start background indexing if RAG is available
        if self.rag_system and hasattr(self.rag_system, "index_async"):
            asyncio.create_task(self.rag_system.index_async())

        try:
            while self.running:
                try:
                    user_input = await self._get_input()
                    should_continue = await self.process_input(user_input)
                    if not should_continue:
                        break
                except KeyboardInterrupt:
                    # Ctrl-C instantly ends the session
                    self.running = False
                    break
                except EOFError:
                    self.console.print()
                    break
        finally:
            self.running = False
            self._auto_save_session()
            self._print_goodbye()

    def _print_welcome(self) -> None:
        """Print welcome message."""
        self.console.print("[bold blue]Henchman-AI[/] - /help for commands, /quit to exit\n")

    def _print_goodbye(self) -> None:
        """Print goodbye message."""
        self.console.print("[dim]Goodbye![/]")

    def _auto_save_session(self) -> None:
        """Auto-save the session if enabled and session has content."""
        if not self.config.auto_save:
            return
        if self.session_manager is None or self.session is None:
            return
        if len(self.session.messages) == 0:
            return

        self.session_manager.save(self.session)

    async def _get_input(self) -> str:
        """Get input from the user.

        Returns:
            User input string.

        Raises:
            KeyboardInterrupt: If user presses Ctrl+C.
            EOFError: If user presses Ctrl+D.
        """
        # Ensure a fresh line for the prompt
        self.console.print()
        return await self.prompt_session.prompt_async(self.config.prompt)

    async def process_input(self, user_input: str) -> bool:
        """Process a single user input.

        Args:
            user_input: The user's input string.

        Returns:
            True to continue running, False to exit.
        """
        # Skip empty input
        stripped = user_input.strip()
        if not stripped:
            return True

        # Handle slash commands
        if is_slash_command(stripped):
            return await self._handle_command(stripped)

        # Expand @file references
        expanded = await expand_at_references(stripped)

        # Run through agent
        await self._run_agent(expanded)
        return True

    async def _handle_command(self, input_text: str) -> bool:
        """Handle a slash command.

        Args:
            input_text: The command input (with leading /).

        Returns:
            True to continue running, False to exit.
        """
        parsed = parse_command(input_text)
        if parsed is None:
            return True

        cmd_name, args = parsed

        # Special handling for /quit
        if cmd_name == "quit":
            return False

        # Special handling for /clear - clear agent history
        if cmd_name == "clear":
            self.agent.clear_history()
            self.renderer.console.clear()
            self.renderer.success("History cleared")
            return True

        # Try to execute the command
        cmd = self.command_registry.get(cmd_name)
        if cmd is None:
            self.renderer.error(f"Unknown command: /{cmd_name}")
            self.renderer.muted("Type /help for available commands")
            return True

        ctx = CommandContext(
            console=self.console,
            args=args,
            agent=self.agent,
            tool_registry=self.tool_registry,
            session=self.session,
            repl=self,
        )
        # Add session_manager and project_hash for /chat command
        if self.session_manager:
            ctx.session_manager = self.session_manager
            from pathlib import Path

            ctx.project_hash = self.session_manager.compute_project_hash(Path.cwd())

        await cmd.execute(ctx)
        return True

    async def _run_agent(self, user_input: str) -> None:
        """Run the agent with user input.

        Args:
            user_input: The processed user input.
        """
        # Record user message to session
        if self.session is not None:
            self.session.messages.append(SessionMessage(role="user", content=user_input))

        # Collect assistant response - now also tracks tool calls for session
        assistant_content: list[str] = []

        from henchman.cli.input import KeyMonitor

        monitor = KeyMonitor()
        self.current_monitor = monitor
        monitor_task = asyncio.create_task(monitor.monitor())

        with self.console.status(self._get_rich_status_message(), spinner="dots") as status_obj:
            # Run the orchestrator stream processing as a separate task so we can cancel it
            agent_task = asyncio.create_task(
                self._process_agent_stream(
                    self.orchestrator.run(user_input), assistant_content, status_obj
                )
            )

        try:
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
                # Small sleep to keep the loop responsive
                await asyncio.sleep(0)

            if not agent_task.done():
                with contextlib.suppress(asyncio.CancelledError):
                    await agent_task
            else:
                # Task finished normally, await it to raise any exceptions
                await agent_task

        except Exception as e:
            self.renderer.error(f"Error: {e}")
        finally:
            # Ensure monitor task is cleaned up
            monitor._stop_event.set()
            await monitor_task

    async def _run_agent_direct(self, role: str, user_input: str) -> None:
        """Run a specific agent directly.

        Args:
            role: Agent role to target.
            user_input: The user's input.
        """
        # Record user message to session
        if self.session is not None:
            self.session.messages.append(SessionMessage(role="user", content=f"[@{role}] {user_input}"))

        assistant_content: list[str] = []

        from henchman.cli.input import KeyMonitor
        monitor = KeyMonitor()
        self.current_monitor = monitor
        monitor_task = asyncio.create_task(monitor.monitor())

        with self.console.status(f"[bold cyan]@{role}[/] thinking...", spinner="dots") as status_obj:
            agent_task = asyncio.create_task(
                self._process_agent_stream(
                    self.orchestrator.run_direct(role, user_input), assistant_content, status_obj
                )
            )

        try:
            while not agent_task.done():
                if monitor.stop_requested or monitor.exit_requested:
                    agent_task.cancel()
                    break
                await asyncio.sleep(0.1)

            if not agent_task.done():
                with contextlib.suppress(asyncio.CancelledError):
                    await agent_task
            else:
                await agent_task
        except Exception as e:
            self.renderer.error(f"Error: {e}")
        finally:
            monitor._stop_event.set()
            await monitor_task

    async def _process_agent_stream(
        self,
        event_stream: AsyncIterator[AgentEvent],
        content_collector: list[str] | None = None,
        status_obj: Status | None = None,  # New parameter
    ) -> None:
        """Process an agent event stream, handling tool calls properly.

        This method collects ALL tool calls from a single response before
        executing them, which is required by the OpenAI API.

        Args:
            event_stream: Async iterator of agent events.
            content_collector: Optional list to collect content for session.
        """
        # Check loop limits before processing (unless unlimited mode)
        if not self.agent.unlimited_mode:
            turn = self.agent.turn
            adaptive_limit = turn.get_adaptive_limit(self.config.base_tool_iterations)

            if turn.is_at_limit(self.config.base_tool_iterations):
                self.renderer.error(
                    f"Reached iteration limit ({adaptive_limit}). "
                    "Stopping to prevent infinite loop. Use /unlimited to bypass."
                )
                return

            if turn.tool_count >= self.config.max_tool_calls_per_turn:
                self.renderer.error(
                    f"Reached tool call limit ({self.config.max_tool_calls_per_turn}). "
                    "Stopping to prevent runaway execution."
                )
                return

            # Warn if spinning
            if turn.is_spinning() and turn.iteration > 2:
                self.renderer.warning(
                    "⚠ Possible loop detected: same tool calls or results repeating. "
                    f"Iteration {turn.iteration}/{adaptive_limit}"
                )

        pending_tool_calls: list[ToolCall] = []
        handled_tool_call_ids: set[str] = set()
        accumulated_content: list[str] = []
        last_agent_id: str | None = None
        # Track whether pending tool calls have been recorded to session
        # (for tool calls handled inline by the orchestrator)
        _session_tool_calls_flushed = False

        async for event in event_stream:
            # Update status continuously
            if status_obj:
                status_obj.update(self._get_rich_status_message())

            if event.source_agent:
                last_agent_id = event.source_agent

            if event.type == EventType.CONTENT:
                # Stream content to console
                self.console.print(event.data, end="")
                if content_collector is not None and event.data:
                    content_collector.append(event.data)
                if event.data:
                    accumulated_content.append(event.data)

            elif event.type == EventType.THOUGHT:
                # Show thinking in muted style
                self.renderer.muted(f"[thinking] {event.data}")

            elif event.type == EventType.CONTEXT_COMPACTED:
                # Notify user that context was compacted
                self.renderer.warning(
                    "Context compacted: older messages summarized to fit model limits"
                )

            elif event.type == EventType.TOOL_CALL_REQUEST:
                # Collect tool call - don't execute yet!
                pending_tool_calls.append(event.data)
                tool_call = event.data
                self.renderer.muted(f"\n[tool] {tool_call.name}({tool_call.arguments})")

            elif event.type == EventType.TOOL_CALL_RESULT:
                # Orchestrator already executed this tool — mark as handled
                result_data = event.data
                if isinstance(result_data, dict):
                    tc_id = result_data.get("tool_call_id", "")
                    handled_tool_call_ids.add(tc_id)
                    result_text = result_data.get("result", "")
                    success = result_data.get("success", True)
                    if success:
                        self.renderer.muted(f"[result] {result_text[:200]}...")
                    else:
                        self.renderer.error(f"[error] {result_text[:200]}")

                    # Record to session: flush assistant tool_calls msg once,
                    # then each tool result as it arrives.
                    if self.session is not None:
                        if not _session_tool_calls_flushed and pending_tool_calls:
                            tool_calls_dicts = [
                                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                                for tc in pending_tool_calls
                            ]
                            self.session.messages.append(
                                SessionMessage(
                                    role="assistant",
                                    content="".join(accumulated_content) if accumulated_content else None,
                                    tool_calls=tool_calls_dicts,
                                    agent_id=last_agent_id,
                                )
                            )
                            accumulated_content.clear()
                            _session_tool_calls_flushed = True

                        self.session.messages.append(
                            SessionMessage(
                                role="tool",
                                content=result_text,
                                tool_call_id=tc_id,
                            )
                        )

            elif event.type == EventType.AGENT_DELEGATED:
                from_agent = event.data.get("from", "unknown")
                to_agent = event.data.get("to", "unknown")
                task = event.data.get("task", "")
                self.renderer.muted(f"\n[{from_agent}] Delegating to [bold cyan]{to_agent}[/]: {task}")

            elif event.type == EventType.AGENT_STARTED:
                agent_name = event.data.get("agent", "agent")
                if status_obj:
                    status_obj.update(f"[{agent_name}] working...")

            elif event.type == EventType.AGENT_COMPLETED:
                agent_name = event.data.get("agent", "agent")
                self.renderer.muted(f"[{agent_name}] completed work")

            elif event.type == EventType.AGENT_MESSAGE:
                to_agent = event.data.get("to", "unknown")
                msg = event.data.get("message", "")
                self.renderer.muted(f"\n[bold cyan]→ {to_agent}[/]: {msg}")

            elif event.type == EventType.FINISHED:
                self.console.print()

            elif event.type == EventType.ERROR:
                self.renderer.error(str(event.data))

        # After the stream ends, record assistant message to session
        # Skip if tool calls were already flushed inline by the orchestrator
        if self.session is not None and not _session_tool_calls_flushed:
            if pending_tool_calls:
                # Convert ToolCall objects to dicts for session storage
                tool_calls_dicts = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in pending_tool_calls
                ]
                self.session.messages.append(
                    SessionMessage(
                        role="assistant",
                        content="".join(accumulated_content) if accumulated_content else None,
                        tool_calls=tool_calls_dicts,
                        agent_id=last_agent_id,
                    )
                )
            elif accumulated_content:
                # Content-only response (no tool calls)
                self.session.messages.append(
                    SessionMessage(
                        role="assistant",
                        content="".join(accumulated_content),
                        agent_id=last_agent_id,
                    )
                )
        elif self.session is not None and _session_tool_calls_flushed and accumulated_content:
            # Record post-tool-execution content as a separate assistant message
            self.session.messages.append(
                SessionMessage(
                    role="assistant",
                    content="".join(accumulated_content),
                    agent_id=last_agent_id,
                )
            )

        # Execute only tool calls that were NOT already handled by the orchestrator
        unhandled_tool_calls = [
            tc for tc in pending_tool_calls if tc.id not in handled_tool_call_ids
        ]
        if unhandled_tool_calls:
            await self._execute_tool_calls(unhandled_tool_calls, content_collector)

    async def _execute_tool_calls(
        self, tool_calls: list[ToolCall], content_collector: list[str] | None = None
    ) -> None:
        """Execute a batch of tool calls and continue the agent loop.

        Args:
            tool_calls: List of tool calls to execute.
            content_collector: Optional list to collect content for session.
        """
        # Increment iteration counter (one batch of tool calls = one iteration)
        self.agent.turn.increment_iteration()

        responded_ids = set()

        # Split tool calls into those that need confirmation and those that don't
        # to allow parallel execution of "safe" tools.
        to_parallel: list[ToolCall] = []
        to_sequential: list[ToolCall] = []

        for tc in tool_calls:
            tool = self.tool_registry.get(tc.name)
            # Use same logic as ToolRegistry.execute for confirmation check
            if tool and (
                tc.name in self.tool_registry._auto_approve_policies
                or tool.needs_confirmation(tc.arguments) is None
            ):
                to_parallel.append(tc)
            else:
                to_sequential.append(tc)

        async def execute_and_record(tc: ToolCall) -> None:
            """Execute a tool call and record the result in the session.

            Args:
                tc: The tool call to execute.
            """
            self.renderer.muted(f"\n[tool] {tc.name}({tc.arguments})")
            result = await self.tool_registry.execute(tc.name, tc.arguments)

            # Record results (thread-safe for agent/session lists)
            responded_ids.add(tc.id)
            self.agent.turn.record_tool_call(
                tool_call_id=tc.id,
                tool_name=tc.name,
                arguments=tc.arguments,
                result=result,
            )
            self.agent.submit_tool_result(tc.id, result.content)
            if self.session is not None:
                self.session.messages.append(
                    SessionMessage(role="tool", content=result.content, tool_call_id=tc.id)
                )

            # Show result
            if result.success:
                self.renderer.muted(f"[result] {result.content[:200]}...")
            else:
                self.renderer.error(f"[error] {result.error}")

        try:
            # 1. Execute parallel group (tools not needing confirmation)
            if to_parallel:
                await asyncio.gather(*(execute_and_record(tc) for tc in to_parallel))

            # 2. Execute sequential group (tools needing confirmation)
            if to_sequential:
                # Suspend key monitor while we might be showing confirmation prompts
                if hasattr(self, "current_monitor") and self.current_monitor:
                    await self.current_monitor.suspend()  # type: ignore[attr-defined]

                try:
                    for tc in to_sequential:
                        await execute_and_record(tc)
                finally:
                    if hasattr(self, "current_monitor") and self.current_monitor:
                        self.current_monitor.resume()  # type: ignore[attr-defined]
        finally:
            # Ensure all tool calls have a response, even if interrupted
            for tool_call in tool_calls:
                if tool_call.id not in responded_ids:
                    cancel_msg = "Tool execution was interrupted or cancelled."
                    self.agent.submit_tool_result(tool_call.id, cancel_msg)
                    if self.session is not None:
                        self.session.messages.append(
                            SessionMessage(
                                role="tool",
                                content=cancel_msg,
                                tool_call_id=tool_call.id,
                            )
                        )

        # Show turn status after tool execution
        self._show_turn_status()

        # Add spacing after tool execution
        self.console.print()

        # Now that ALL results are submitted, continue the agent loop
        await self._process_agent_stream(self.agent.continue_with_tool_results(), content_collector)

    def _show_turn_status(self) -> None:
        """Display current turn status."""
        turn = self.agent.turn
        status = turn.get_status_string(
            base_limit=self.config.base_tool_iterations,
            max_tokens=self.agent.max_tokens,
        )

        # Color based on status
        if turn.is_spinning() or turn.is_approaching_limit(self.config.base_tool_iterations):
            self.renderer.warning(status)
        else:
            self.renderer.muted(status)

    async def _handle_agent_event(
        self, event: AgentEvent, content_collector: list[str] | None = None
    ) -> None:
        """Handle an event from the agent.

        DEPRECATED: Use _process_agent_stream instead for proper tool call handling.
        This method is kept for backwards compatibility with tests.

        Args:
            event: The agent event to handle.
            content_collector: Optional list to collect content for session recording.
        """
        if event.type == EventType.CONTENT:
            # Stream content to console
            self.console.print(event.data, end="")
            # Collect for session recording
            if content_collector is not None and event.data:
                content_collector.append(event.data)

        elif event.type == EventType.THOUGHT:
            # Show thinking in muted style
            self.renderer.muted(f"[thinking] {event.data}")

        elif event.type == EventType.TOOL_CALL_REQUEST:
            # NOTE: In the new flow, tool calls are batched and handled by
            # _process_agent_stream. This path is only for backwards compat.
            pass

        elif event.type == EventType.FINISHED:
            # Print newline after streaming content
            self.console.print()

        elif event.type == EventType.ERROR:
            self.renderer.error(str(event.data))  # pragma: no branch

    async def _handle_tool_call(self, tool_call: ToolCall) -> None:
        """Handle a single tool call from the agent.

        DEPRECATED: Use _execute_tool_calls for proper batched handling.
        This method is kept for backwards compatibility with tests.

        Args:
            tool_call: The tool call to execute.
        """
        if not isinstance(tool_call, ToolCall):
            return

        self.renderer.muted(f"\n[tool] {tool_call.name}({tool_call.arguments})")

        # Execute the tool
        result = await self.tool_registry.execute(tool_call.name, tool_call.arguments)

        # Submit result to agent
        self.agent.submit_tool_result(tool_call.id, result.content)

        # Show result
        if result.success:
            self.renderer.muted(f"[result] {result.content[:200]}...")
        else:
            self.renderer.error(f"[error] {result.error}")

        # NOTE: In the new flow, continue_with_tool_results is called
        # after ALL tool calls are processed. For backwards compat with
        # tests that call this method directly, we don't call continue here.
