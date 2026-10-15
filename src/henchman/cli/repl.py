"""REPL (Read-Eval-Print Loop) for interactive mode.

This module provides the main interactive loop for the CLI.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.text import Text

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.command_processor import CommandProcessor
from henchman.cli.input_handler import InputHandler
from henchman.cli.output_handler import OutputHandler, resolve_active_agent
from henchman.cli.plugins import PluginManager
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.stream_event_handlers import build_confirmation_message
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.tool_manager import ToolManager
from henchman.cli.ui_renderer import UIRenderer
from henchman.core.eventbus import EventBus
from henchman.core.events import EventType
from henchman.core.goals import GoalService, save_goal_session
from henchman.mcp.manager import McpManager

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from prompt_toolkit.key_binding import KeyPressEvent

    from henchman.cli.input import KeyMonitor
    from henchman.config.schema import Settings
    from henchman.core.agent import Agent
    from henchman.core.events import AgentEvent
    from henchman.core.session import Session
    from henchman.providers.base import ModelProvider, ToolCall
    from henchman.tools.base import ConfirmationRequest


try:
    from typing import Self
except ImportError:  # pragma: no cover
    from typing import Self

_DEFAULT_BASE_TOOL_ITERATIONS: int = 25
_DEFAULT_MAX_TOOL_CALLS_PER_TURN: int = 100
_MONITOR_POLL_INTERVAL: float = 0.1
_MONITOR_CLEANUP_TIMEOUT: float = 1.0
_VISIBLE_TURN_EVENT_TYPES = frozenset(
    {
        EventType.CONTENT,
        EventType.THOUGHT,
        EventType.CONTEXT_COMPACTED,
        EventType.TOOL_CALL_REQUEST,
        EventType.TOOL_CALL_RESULT,
        EventType.AGENT_DELEGATED,
        EventType.AGENT_MESSAGE,
        EventType.AGENT_COMPLETED,
        EventType.ERROR,
    }
)

logger = logging.getLogger(__name__)


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
        interactive: Whether tools may collect answers from the terminal.
    """

    prompt: str = "❯ "
    system_prompt: str = ""
    auto_save: bool = True
    history_file: Path | None = None
    base_tool_iterations: int = _DEFAULT_BASE_TOOL_ITERATIONS
    max_tool_calls_per_turn: int = _DEFAULT_MAX_TOOL_CALLS_PER_TURN
    auto_approve_tools: bool = False
    agent_role: str | None = None
    interactive: bool = True


@dataclass
class _QueuedInput:
    """A user message or state-changing command waiting for exclusive agent access."""

    message: str
    role: str | None = None
    command: bool = False


async def _run_monitored_task(
    event_stream: AsyncIterator[AgentEvent],
    agent: Agent,
    assistant_content: list[str],
    tool_executor: ToolExecutor,
    monitor: KeyMonitor,
) -> tuple[bool, bool]:
    """Execute the agent task and poll for monitor cancellation signals.

    Returns:
        Tuple of (exit_requested, stop_requested).
    """
    agent_task = asyncio.create_task(
        tool_executor.process_agent_stream(
            event_stream,
            agent,
            assistant_content,
            None,
        ),
    )
    exit_requested = False
    stop_requested = False

    try:
        while not agent_task.done():
            if monitor.exit_requested:
                agent_task.cancel()
                exit_requested = True
                break
            if monitor.stop_requested:
                agent_task.cancel()
                stop_requested = True
                break
            await asyncio.sleep(_MONITOR_POLL_INTERVAL)

        with contextlib.suppress(asyncio.CancelledError):
            await agent_task

        return exit_requested, stop_requested
    finally:
        # Outer task cancellation can arrive during polling, before we await the
        # worker. Join it before the caller snapshots the conversation history.
        if not agent_task.done():
            agent_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await agent_task


async def _cleanup_monitor(
    monitor: KeyMonitor,
    monitor_task: asyncio.Task[None],
) -> None:
    """Signal monitor to stop and wait for it to finish with a timeout."""
    if hasattr(monitor, "_stop_event"):
        monitor._stop_event.set()
    try:
        await asyncio.wait_for(monitor_task, timeout=_MONITOR_CLEANUP_TIMEOUT)
    except (TimeoutError, asyncio.CancelledError):
        monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor_task


def _is_visible_turn_activity(event: AgentEvent) -> bool:
    """Return whether the prompt-toolkit REPL renders an event visibly."""
    if event.type in {EventType.CONTENT, EventType.THOUGHT}:
        return bool(event.data)
    if event.type == EventType.TOOL_CALL_RESULT:
        return isinstance(event.data, dict)
    return event.type in _VISIBLE_TURN_EVENT_TYPES


async def _with_first_visible_activity_callback(
    event_stream: AsyncIterator[AgentEvent],
    callback: Callable[[], None],
) -> AsyncIterator[AgentEvent]:
    """Run a callback before yielding the stream's first visible event."""
    activity_started = False
    try:
        async for event in event_stream:
            if not activity_started and _is_visible_turn_activity(event):
                callback()
                activity_started = True
            yield event
    finally:
        close = getattr(event_stream, "aclose", None)
        if close is not None:
            await close()


def _collect_event_content(
    event: AgentEvent,
    content_collector: list[str] | None,
    render_error: Callable[[str], None],
) -> None:
    """Route an agent event to error display or content collection."""
    if event.type == EventType.ERROR:
        render_error(str(event.data))
    elif event.type == EventType.CONTENT and content_collector is not None and event.data:
        content_collector.append(event.data)


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
        self: Self,
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
        self.event_bus = EventBus()
        self.running = False
        self.rag_system: object | None = None
        self.current_monitor: KeyMonitor | None = None
        self._question_lock = asyncio.Lock()
        self._terminal_lock = asyncio.Lock()
        self._chat_input_ready = asyncio.Event()
        self._chat_input_ready.set()
        self._prompt_task: asyncio.Task[str] | None = None
        self._interactive_loop_active = False
        self._pending_inputs: deque[_QueuedInput] = deque()
        self._turn_worker: asyncio.Task[None] | None = None

        self.renderer = self._init_renderer(renderer)
        self._init_mcp_manager()
        self.session_manager = ReplSessionManager(auto_save=self.config.auto_save)
        self._init_tool_manager()
        self._init_plugin_manager()
        self.orchestrator = self._init_orchestrator(environment_context)
        self.agent = self.orchestrator.tech_lead
        self._init_handlers()
        self._init_tool_executor()
        self._init_input_handler()

    def _init_renderer(self: Self, renderer: UIRenderer | None) -> UIRenderer:
        """Create UI renderer with settings-based configuration."""
        if renderer:
            return renderer
        ui = self.settings.ui if self.settings else None
        return UIRenderer(
            console=self.console,
            accessible_mode=ui.accessible_mode if ui else False,
            style_overrides=ui.style_overrides if ui else None,
            layout_settings=getattr(ui, "layout", None) if ui else None,
        )

    def _init_tool_manager(self: Self) -> None:
        """Initialize tool manager and expose its registry."""
        self.tool_manager = ToolManager(
            settings=self.settings,
            question_handler=self._ask_question if self.config.interactive else None,
        )
        self.tool_manager.set_auto_approve(auto_approve=self.config.auto_approve_tools)
        self.tool_manager.bind_runtime(
            project_root=Path.cwd(),
            session_manager=self.session_manager,
            mcp_manager=self.mcp_manager,
        )
        self.tool_manager.register_builtin_tools()
        self.tool_registry = self.tool_manager.registry  # Backwards compatibility

    @contextlib.asynccontextmanager
    async def _exclusive_terminal(self) -> AsyncIterator[None]:
        """Suspend chat input while one question or approval owns the terminal."""
        async with self._question_lock:
            self._chat_input_ready.clear()
            monitor = self.current_monitor
            try:
                prompt = self._prompt_task
                if prompt is not None and not prompt.done():
                    session = self.input_handler.prompt_session
                    if session is not None and session.app.is_running:
                        buffer = session.default_buffer
                        document = buffer.document
                        session.app.pre_run_callables.append(lambda: buffer.set_document(document))
                    prompt.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await prompt
                async with self._terminal_lock:
                    if monitor is not None:
                        await monitor.suspend()
                    try:
                        yield
                    finally:
                        if monitor is not None:
                            monitor.resume()
            except asyncio.CancelledError:
                self._pause_goal()
                raise
            finally:
                self._chat_input_ready.set()

    async def _ask_question(self, question: str) -> str | None:
        """Give one question exclusive terminal ownership until it finishes."""
        async with self._exclusive_terminal():
            return await self.input_handler.ask_question(question)

    def _init_mcp_manager(self: Self) -> None:
        """Create MCP manager if servers are configured in settings."""
        self.mcp_manager: McpManager | None = None
        if self.settings and self.settings.mcp_servers:
            mcp_logging = self.settings.ui.mcp_logging if self.settings.ui else False
            self.mcp_manager = McpManager.create_from_settings(
                self.settings,
                mcp_logging_enabled=mcp_logging,
            )

    def _init_plugin_manager(self: Self) -> None:
        """Load plugins from home and workspace plugin directories."""
        self.plugin_manager = PluginManager(self)
        for plugin_directory in (
            Path.home() / ".henchman" / "plugins",
            Path.cwd() / ".henchman" / "plugins",
        ):
            self.plugin_manager.load_plugins_from_directory(plugin_directory)

    def _init_orchestrator(self: Self, environment_context: str | None) -> Orchestrator:
        """Create the orchestrator with provider, tools, and event bus."""
        return Orchestrator(
            default_provider=self.provider,
            tool_registry=self.tool_registry,
            event_bus=self.event_bus,
            settings=self.settings,
            system_prompt=self.config.system_prompt,
            environment_context=environment_context,
        )

    def _init_handlers(self: Self) -> None:
        """Create output handler and command processor wired to shared subsystems."""
        self.output_handler = OutputHandler(
            renderer=self.renderer,
            tool_manager=self.tool_manager,
            session_manager=self.session_manager,
            provider=self.provider,
            settings=self.settings,
            rag_system=self.rag_system,
            mcp_manager=self.mcp_manager,
        )
        self.command_processor = CommandProcessor(
            output_handler=self.output_handler,
            tool_manager=self.tool_manager,
            session_manager=self.session_manager,
            provider=self.provider,
            mcp_manager=self.mcp_manager,
        )

    def _init_tool_executor(self: Self) -> None:
        """Create tool executor and wire its confirmation handler."""
        self.tool_executor = ToolExecutor(
            output_handler=self.output_handler,
            tool_manager=self.tool_manager,
            provider=self.provider,
            base_tool_iterations=self.config.base_tool_iterations,
            max_tool_calls_per_turn=self.config.max_tool_calls_per_turn,
        )
        self.tool_manager.set_confirmation_handler(
            self._handle_confirmation,
        )

    def _init_input_handler(self: Self) -> None:
        """Create input handler and initialise its prompt session."""
        history_file = self.config.history_file or Path.home() / ".henchman_history"
        keybindings = self.settings.ui.keybindings if self.settings and self.settings.ui else None
        self.input_handler = InputHandler(
            config=self.config,
            renderer=self.renderer,
            history_file=history_file,
            keybindings=keybindings,
            tool_registry=self.tool_registry,
        )
        self.input_handler.initialize_prompt_session(
            bottom_toolbar=lambda: self.output_handler.get_toolbar_status(resolve_active_agent(self)),
        )
        prompt = self.input_handler.prompt_session
        if prompt is not None:
            bindings = KeyBindings()

            @bindings.add("escape", filter=Condition(self._has_active_turn))
            @bindings.add("c-c", filter=Condition(self._has_active_turn))
            def interrupt(_event: KeyPressEvent) -> None:
                self.interrupt_agent()

            existing = prompt.key_bindings
            prompt.key_bindings = merge_key_bindings(
                [existing, bindings] if existing is not None else [bindings],
            )

    def _has_active_turn(self) -> bool:
        """Enable turn cancellation bindings while interactive work is running."""
        return self._turn_worker is not None and not self._turn_worker.done()


    def set_session(self: Self, session: Session) -> None:
        """Set the current session and sync with agent history.

        Args:
            session: The session to activate.

        Returns:
            None
        """
        history_agent = (
            self.orchestrator.pool.get_agent(self.config.agent_role)
            if self.config.agent_role else self.agent
        )
        self.session_manager.set_session(session, history_agent=history_agent)

    async def _handle_confirmation(self: Self, request: ConfirmationRequest) -> bool:
        """Handle a tool confirmation request from the registry.

        Args:
            request: The confirmation request data.

        Returns:
            True if approved, False otherwise.
        """
        async with self._exclusive_terminal():
            if self._interactive_loop_active:
                message = Text.from_markup(build_confirmation_message(request)).plain
                answer = await self.input_handler.ask_question(f"{message} [y/N]")
                return answer is not None and answer.strip().lower() in {"y", "yes"}
            return await self.tool_executor.handle_confirmation(request)

    async def initialize_mcp(self: Self) -> None:
        """Initialize MCP servers and register tools.

        This method can be called separately for headless mode.

        Returns:
            None
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
                        f"Connected to {len(self.mcp_manager.clients)} MCP server(s) with {len(self.mcp_manager.get_all_tools())} tools",
                    )
            except Exception as e:
                # Always show errors, regardless of logging setting
                self.renderer.error(f"Failed to connect to MCP servers: {e}")

    async def run(self: Self) -> None:
        """Run the main REPL loop.

        This method runs until the user exits with /quit, Ctrl+C, or Ctrl+D.

        Returns:
            None
        """
        self.running = True
        self._interactive_loop_active = True
        self.output_handler.print_welcome()
        await self.initialize_mcp()

        # Start background indexing if RAG is available
        self.output_handler.start_background_indexing()

        # Render asynchronous output above the editable prompt, retaining Rich ANSI styling.
        with patch_stdout(raw=True):
            try:
                self._ensure_turn_worker()
                while self.running:
                    if not await self._process_one_turn():
                        break
            finally:
                self.running = False
                self._interactive_loop_active = False
                await self._stop_turn_worker()
                self._pause_goal()
                if self.mcp_manager:
                    await self.mcp_manager.disconnect_all()
                self._auto_save_session()
                self.output_handler.print_goodbye()

    async def _process_one_turn(self: Self) -> bool:
        """Process one input turn, handling keyboard interrupts.

        Returns:
            True to continue running, False to exit.
        """
        try:
            user_input = await self._get_input()
            return await self.process_input(user_input)
        except KeyboardInterrupt:
            if self._turn_worker is not None and not self._turn_worker.done():
                self.interrupt_agent()
                return True
            self._pause_goal()
            self.running = False
            return False
        except EOFError:
            self.renderer.print_newline()
            return False

    def _auto_save_session(self: Self) -> None:
        """Auto-save the session if enabled and session has content."""
        self.session_manager.auto_save_session()

    async def _get_input(self: Self) -> str:
        """Get input from the user.

        Returns:
            User input string.

        Raises:
            KeyboardInterrupt: If user presses Ctrl+C.
            EOFError: If user presses Ctrl+D.
        """
        while True:
            await self._chat_input_ready.wait()
            async with self._terminal_lock:
                if not self._chat_input_ready.is_set():
                    continue
                self._prompt_task = asyncio.create_task(self.input_handler.get_input())
                try:
                    return await self._prompt_task
                except asyncio.CancelledError:
                    current = asyncio.current_task()
                    if current is not None and current.cancelling():
                        raise
                    if self._chat_input_ready.is_set():
                        raise
                finally:
                    self._prompt_task = None

    async def process_input(self: Self, user_input: str) -> bool:
        """Process a single user input.

        Args:
            user_input: The user's input string.

        Returns:
            True to continue running, False to exit.
        """
        # Use InputHandler to process input
        processed_input, is_command, should_continue = await self.input_handler.process_input(
            user_input,
        )

        if not should_continue:
            return False

        # Skip empty input (already processed by InputHandler, but double-check)
        if not processed_input:
            return True

        if is_command:
            command_name = processed_input.split(maxsplit=1)[0].lower()
            if self._interactive_loop_active and command_name in {
                "/clear", "/chat", "/session", "/model", "/plan", "/mcp",
                "/context", "/team", "/unlimited",
            }:
                self._pending_inputs.append(_QueuedInput(processed_input, command=True))
                self._ensure_turn_worker()
                return True
            # Goal controls and informational commands remain immediately available.
            should_continue = await self.command_processor.handle_command(
                processed_input,
                resolve_active_agent(self),
                self,
            )
            if should_continue and self._interactive_loop_active:
                self._ensure_turn_worker()
            return should_continue

        # Interactive input stays responsive while one worker serializes turns.
        await self.submit_agent_input(processed_input)
        return True

    async def submit_agent_input(self, user_input: str) -> None:
        """Queue interactive work; preserve awaited execution for direct callers."""
        if not self._interactive_loop_active:
            await self._run_agent(user_input)
            return
        self._pending_inputs.append(_QueuedInput(user_input))
        self._ensure_turn_worker()
        await asyncio.sleep(0)

    def _ensure_turn_worker(self) -> None:
        """Start at most one worker when user input or an active goal needs work."""
        if not self._interactive_loop_active:
            return
        if self._turn_worker is not None and not self._turn_worker.done():
            return
        if self._pending_inputs or GoalService().continuation_prompt(self.session_manager.current):
            self._turn_worker = asyncio.create_task(self._drain_agent_inputs())
            self._turn_worker.add_done_callback(self._turn_worker_finished)

    def _turn_worker_finished(self, task: asyncio.Task[None]) -> None:
        """Release the worker and preserve messages queued during cancellation."""
        if self._turn_worker is task:
            self._turn_worker = None
        if not task.cancelled():
            error = task.exception()
            if error is not None:
                logger.error("Interactive turn failed", exc_info=error)
                self.renderer.error(f"Error: {error}")
                self._pause_goal()
        if self._pending_inputs:
            self._ensure_turn_worker()

    async def _drain_agent_inputs(self) -> None:
        """Run user messages before autonomous continuations, without overlapping turns."""
        message: str | None
        while self._interactive_loop_active:
            await asyncio.sleep(0)
            if self._pending_inputs:
                pending = self._pending_inputs.popleft()
            else:
                message = GoalService().continuation_prompt(self.session_manager.current)
                if message is None:
                    return
                pending = _QueuedInput(message)
            if pending.command:
                await self.command_processor.handle_command(
                    pending.message, resolve_active_agent(self), self,
                )
            elif pending.role is None:
                await self._run_agent(pending.message)
            else:
                await self._run_agent_direct(pending.role, pending.message)

    def _pause_goal(self) -> None:
        """Persist goal suspension when the user interrupts or leaves the REPL."""
        manager = getattr(self, "session_manager", None)
        session = manager.current if manager is not None else None
        service = GoalService()
        goal = service.get(session)
        if session is not None and goal is not None and goal.status == "active":
            service.pause(session)
            save_goal_session(manager, session)

    def interrupt_agent(self) -> None:
        """Pause autonomous work and cancel the current interactive turn."""
        self._pause_goal()
        if self._turn_worker is not None and not self._turn_worker.done():
            self._turn_worker.cancel()
            self.renderer.warning("Interrupted; active goal paused.")

    async def _stop_turn_worker(self) -> None:
        """Cancel and join in-flight work before shutdown or a session change."""
        task = self._turn_worker
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            self._turn_worker = None

    async def _run_agent(self: Self, user_input: str) -> None:
        """Run the agent with user input.

        Args:
            user_input: The processed user input.
        """
        if self.config.agent_role:
            await self._run_agent_direct(self.config.agent_role, user_input)
            return
        session = self.session_manager.current
        session_start = len(session.messages) if session else 0
        turn_number = self.agent._turn_number
        self.session_manager.record_user_message(user_input)
        assistant_content: list[str] = []
        try:
            await self._run_agent_with_monitor(
                self.orchestrator.run(user_input),
                self.agent,
                assistant_content,
                None,
            )
        finally:
            if self.agent._turn_number != turn_number:
                self.session_manager.sync_agent_turn(self.agent, session_start=session_start)
            self.session_manager.auto_save_session()

    async def _run_agent_direct(self: Self, role: str, user_input: str) -> None:
        """Run a specific agent directly.

        Args:
            role: Agent role to target.
            user_input: The user's input.
        """
        if (
            getattr(self, "_interactive_loop_active", False)
            and asyncio.current_task() is not self._turn_worker
        ):
            self._pending_inputs.append(_QueuedInput(user_input, role=role))
            self._ensure_turn_worker()
            return
        agent = self.orchestrator.pool.get_agent(role)
        session = self.session_manager.current
        session_start = len(session.messages) if session else 0
        turn_number = agent._turn_number
        self.session_manager.record_user_message(user_input)
        assistant_content: list[str] = []
        try:
            await self._run_agent_with_monitor(
                self.orchestrator.run_direct(role, user_input),
                agent,
                assistant_content,
                f"@{role}",
            )
        finally:
            if agent._turn_number != turn_number:
                self.session_manager.sync_agent_turn(agent, session_start=session_start)
            self.session_manager.auto_save_session()

    async def _observe_goal_errors(
        self, event_stream: AsyncIterator[AgentEvent],
    ) -> AsyncIterator[AgentEvent]:
        """Stop automatic retries when an agent reports a provider or runtime error."""
        try:
            async for event in event_stream:
                if event.type == EventType.ERROR:
                    self._pause_goal()
                yield event
        finally:
            close = getattr(event_stream, "aclose", None)
            if close is not None:
                await close()

    async def _run_agent_with_monitor(
        self: Self,
        event_stream: AsyncIterator[AgentEvent],
        agent: Agent,
        assistant_content: list[str],
        status_detail: str | None,
    ) -> None:
        """Run agent with monitor setup and cancellation handling.

        Args:
            event_stream: Agent event stream.
            agent: The agent to run.
            assistant_content: List to collect assistant content.
            status_detail: Optional plain-text detail for the transient status.
        """
        from henchman.cli.input import KeyMonitor

        interactive = getattr(self, "_interactive_loop_active", False)
        monitor = None if interactive else KeyMonitor()
        self.current_monitor = monitor
        monitor_task = asyncio.create_task(monitor.monitor()) if monitor is not None else None
        thinking_active = False

        def stop_thinking() -> None:
            nonlocal thinking_active
            if thinking_active:
                self.renderer.stop_thinking()
                thinking_active = False

        try:
            self.renderer.start_thinking(status_detail)
            thinking_active = True

            stream = _with_first_visible_activity_callback(
                self._observe_goal_errors(event_stream), stop_thinking,
            )
            if monitor is None:
                await self.tool_executor.process_agent_stream(stream, agent, assistant_content, None)
                exit_req, stop_req = False, False
            else:
                exit_req, stop_req = await _run_monitored_task(
                    stream, agent, assistant_content, self.tool_executor, monitor,
                )
            stop_thinking()

            if exit_req or stop_req:
                self._pause_goal()
            if exit_req:
                self.renderer.warning("\n[Exit requested by Ctrl+C]")
                self.running = False
            elif stop_req:
                self.renderer.warning("\n[Interrupted by Esc]")

        except Exception as e:
            stop_thinking()
            self._pause_goal()
            logger.exception("Agent execution failed: %s", e)
            self.renderer.error(f"Error: {e}")
        finally:
            stop_thinking()
            if monitor is not None and monitor_task is not None:
                await _cleanup_monitor(monitor, monitor_task)
            self.current_monitor = None

    async def _handle_agent_event(
        self: Self,
        event: AgentEvent,
        content_collector: list[str] | None = None,
    ) -> None:
        """Handle an event from the agent.

        DEPRECATED: Use ToolExecutor.process_agent_stream instead.
        This method is kept for backwards compatibility with tests.
        """
        _collect_event_content(event, content_collector, self.renderer.error)

    async def _handle_tool_call(self: Self, tool_call: ToolCall) -> None:
        """Handle a single tool call from the agent.

        DEPRECATED: Use ToolExecutor.execute_tool_calls for proper batched handling.
        This method is kept for backwards compatibility with tests.

        Args:
            tool_call: The tool call to execute.
        """
        # Convert single tool call to list for execute_tool_calls
        await self.tool_executor.execute_tool_calls([tool_call], self.agent)
