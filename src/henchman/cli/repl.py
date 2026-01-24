"""REPL (Read-Eval-Print Loop) for interactive mode.

This module provides the main interactive loop for the CLI.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from henchman.cli.commands import CommandContext, CommandRegistry, parse_command
from henchman.cli.commands.builtins import get_builtin_commands
from henchman.cli.console import OutputRenderer
from henchman.cli.input import create_session, expand_at_references, is_slash_command
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.core.session import Session, SessionManager, SessionMessage
from henchman.providers.base import ModelProvider, ToolCall
from henchman.tools.registry import ToolRegistry
from henchman.utils.tokens import TokenCounter


@dataclass
class ReplConfig:
    """Configuration for the REPL.

    Attributes:
        prompt: The prompt string to display.
        system_prompt: System prompt for the agent.
        auto_save: Whether to auto-save sessions.
    """

    prompt: str = "❯ "
    system_prompt: str = ""
    auto_save: bool = True


class Repl:
    """The main REPL (Read-Eval-Print Loop) for interactive mode.

    The Repl class orchestrates the main interaction loop, connecting
    the agent, tools, commands, and UI components.
    """

    def __init__(
        self,
        provider: ModelProvider,
        console: Console,
        config: ReplConfig | None = None,
        session_manager: SessionManager | None = None,
    ) -> None:
        """Initialize the REPL.

        Args:
            provider: The model provider to use.
            console: Rich console for output.
            config: REPL configuration.
            session_manager: Optional session manager for saving sessions.
        """
        self.provider = provider
        self.console = console
        self.config = config or ReplConfig()
        self.session_manager = session_manager
        self.session: Session | None = None

        # Initialize components
        self.agent = Agent(provider, system_prompt=self.config.system_prompt)
        self.tool_registry = ToolRegistry()
        self.command_registry = CommandRegistry()
        self.renderer = OutputRenderer(console)
        self.prompt_session = create_session()

        # Register built-in commands
        for cmd in get_builtin_commands():
            self.command_registry.register(cmd)

        # Initialize session if manager is provided
        if self.session_manager is not None:
            self.session = self.session_manager.create()

        # Track REPL state
        self.running = False
        
        # Track if agent is currently running (for interruption)
        self.agent_running = False
        self._agent_task = None
        
        # Track Ctrl+C timing for double-tap exit
        self._last_interrupt_time = None

    async def run(self) -> None:
        """Run the main REPL loop.

        This method runs until the user exits with /quit, Ctrl+C, or Ctrl+D.
        """
        self.running = True
        self._print_welcome()

        try:
            while self.running:
                try:
                    user_input = await self._get_input()
                    should_continue = await self.process_input(user_input)
                    if not should_continue:
                        break
                except KeyboardInterrupt:
                    # Ctrl+C handling with double-tap to exit
                    current_time = time.time()
                    
                    # Check if this is a double Ctrl+C within 2 seconds
                    if self._last_interrupt_time is not None:
                        time_since_last = current_time - self._last_interrupt_time
                        if time_since_last < 2.0:  # Double Ctrl+C within 2 seconds
                            self.console.print("\n[bold red]Exiting...[/]")
                            break  # Exit the REPL
                    
                    # Check if agent is running and interrupt it
                    if self.agent_running and self._agent_task:
                        self.console.print("\n[dim]Interrupting agent...[/]")
                        self._agent_task.cancel()
                        try:
                            await self._agent_task
                        except asyncio.CancelledError:
                            pass
                        self.agent_running = False
                        self._agent_task = None
                    
                    # First Ctrl+C or spaced out
                    self.console.print("\n[dim]Press Ctrl+C again to exit[/]")
                    self._last_interrupt_time = current_time
                    continue
                except EOFError:
                    self.console.print()
                    break
        finally:
            self.running = False
            self._auto_save_session()
            self._print_goodbye()

    def _print_welcome(self) -> None:
        """Print welcome message."""
        self.console.print(
            "[bold blue]Henchman-AI[/] - /help for commands, /quit to exit\n"
        )

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
        )
        await cmd.execute(ctx)
        return True

    async def _run_agent(self, user_input: str) -> None:
        """Run the agent with user input.

        Args:
            user_input: The processed user input.
        """
        # Mark agent as running
        self.agent_running = True
        self._agent_task = asyncio.current_task()
        
        # Record user message to session
        if self.session is not None:
            self.session.messages.append(SessionMessage(role="user", content=user_input))

        # Collect assistant response
        assistant_content: list[str] = []

        try:
            async for event in self.agent.run(user_input):
                await self._handle_agent_event(event, assistant_content)
        except Exception as e:
            self.renderer.error(f"Error: {e}")
        finally:
            # Mark agent as not running
            self.agent_running = False
            self._agent_task = None

        # Record assistant response to session
        if self.session is not None and assistant_content:
            self.session.messages.append(
                SessionMessage(role="assistant", content="".join(assistant_content))
            )

    async def _handle_agent_event(
        self, event: AgentEvent, content_collector: list[str] | None = None
    ) -> None:
        """Handle an event from the agent.

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
            # Handle tool call
            await self._handle_tool_call(event.data)

        elif event.type == EventType.FINISHED:
            # Print newline after streaming content
            self.console.print()

        elif event.type == EventType.ERROR:
            self.renderer.error(str(event.data))  # pragma: no branch

    async def _handle_tool_call(self, tool_call: ToolCall) -> None:
        """Handle a tool call from the agent.

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

        # Continue with tool results
        async for event in self.agent.continue_with_tool_results():
            await self._handle_agent_event(event)
