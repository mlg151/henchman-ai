"""Refactored version of _run_headless function with extracted methods and classes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from henchman.cli.console import OutputRenderer, ThemeManager
from henchman.cli.json_output import JsonOutputRenderer
from henchman.cli.repl import Repl, ReplConfig
from henchman.cli.ui_renderer import UIRenderer
from henchman.config import ContextLoader, load_settings
from henchman.config.environment import format_environment_block, gather_environment
from henchman.core.events import AgentEvent, EventType
from henchman.rag import initialize_rag

if TYPE_CHECKING:
    from henchman.providers.base import ModelProvider


@dataclass
class HeadlessConfig:
    """Configuration for headless mode execution."""
    prompt: str
    output_format: str
    plan_mode: bool = False
    auto_approve: bool = False
    agent_role: str | None = None


@dataclass
class HeadlessContext:
    """Shared context for headless mode execution."""
    provider: ModelProvider
    settings: object
    system_prompt: str
    environment_block: str
    repl: Repl
    rag_system: object | None = None


class OutputStrategy(Protocol):
    """Protocol for different output strategies in headless mode."""
    
    async def run(self, context: HeadlessContext, config: HeadlessConfig) -> None:
        """Execute the strategy with the given context and configuration."""
        ...


class TextOutputStrategy:
    """Strategy for text output format."""
    
    async def run(self, context: HeadlessContext, config: HeadlessConfig) -> None:
        """Process a single prompt and exit with text output."""
        # Initialize MCP servers
        await context.repl.initialize_mcp()

        if context.rag_system:
            asyncio.create_task(context.rag_system.index_async())  # type: ignore[attr-defined]

        if config.agent_role:
            await context.repl._run_agent_direct(config.agent_role, config.prompt)
        else:
            await context.repl.process_input(config.prompt)


class JsonOutputStrategy:
    """Strategy for JSON output format."""
    
    def __init__(self, console):
        self.console = console
    
    async def run(self, context: HeadlessContext, config: HeadlessConfig) -> None:
        """Process a single prompt and exit with JSON output."""
        # Initialize MCP servers
        await context.repl.initialize_mcp()

        if context.rag_system:
            asyncio.create_task(context.rag_system.index_async())  # type: ignore[attr-defined]

        json_renderer = JsonOutputRenderer(self.console)

        async def run_and_render(stream: AsyncIterator[AgentEvent]) -> None:
            """Run the agent stream and render events to JSON.

            Args:
                stream: The stream of agent events.
            """
            pending_tool_calls = []
            async for event in stream:
                json_renderer.render(event)
                if event.type == EventType.TOOL_CALL_REQUEST:
                    pending_tool_calls.append(event.data)

            if pending_tool_calls:
                # Execute tool calls
                for tool_call in pending_tool_calls:
                    result = await context.repl.tool_registry.execute(
                        tool_call.name, tool_call.arguments
                    )
                    context.repl.agent.submit_tool_result(tool_call.id, result.content)
                    # Emit tool result event
                    json_renderer.render(AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result))

                # Continue
                await run_and_render(context.repl.agent.continue_with_tool_results())

        await run_and_render(context.repl.agent.run(config.prompt))


class StreamJsonOutputStrategy:
    """Strategy for streaming JSON output format."""
    
    def __init__(self, console):
        self.console = console
    
    async def run(self, context: HeadlessContext, config: HeadlessConfig) -> None:
        """Process a single prompt and exit with streaming JSON output."""
        # Initialize MCP servers
        await context.repl.initialize_mcp()

        if context.rag_system:
            asyncio.create_task(context.rag_system.index_async())  # type: ignore[attr-defined]

        json_renderer = JsonOutputRenderer(self.console)

        async def run_and_render_stream(stream: AsyncIterator[AgentEvent]) -> None:
            """Run the agent stream and render events.

            Args:
                stream: The stream of agent events.
            """
            pending_tool_calls = []
            async for event in stream:
                json_renderer.render_stream_json(event)
                if event.type == EventType.TOOL_CALL_REQUEST:
                    pending_tool_calls.append(event.data)

            if pending_tool_calls:
                for tool_call in pending_tool_calls:
                    result = await context.repl.tool_registry.execute(
                        tool_call.name, tool_call.arguments
                    )
                    context.repl.agent.submit_tool_result(tool_call.id, result.content)
                    json_renderer.render_stream_json(
                        AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result)
                    )

                await run_and_render_stream(context.repl.agent.continue_with_tool_results())

        await run_and_render_stream(context.repl.agent.run(config.prompt))


class CompleteJsonOutputStrategy:
    """Strategy for complete JSON output format."""
    
    def __init__(self, console):
        self.console = console
    
    async def run(self, context: HeadlessContext, config: HeadlessConfig) -> None:
        """Process a single prompt and exit with complete JSON output."""
        # Initialize MCP servers
        await context.repl.initialize_mcp()

        if context.rag_system:
            asyncio.create_task(context.rag_system.index_async())  # type: ignore[attr-defined]

        json_renderer = JsonOutputRenderer(self.console)
        all_events: list[AgentEvent] = []

        async def run_and_collect(stream: AsyncIterator[AgentEvent]) -> None:
            """Run the agent stream and collect all events.

            Args:
                stream: The stream of agent events.
            """
            pending_tool_calls = []
            async for event in stream:
                all_events.append(event)
                if event.type == EventType.TOOL_CALL_REQUEST:
                    pending_tool_calls.append(event.data)

            if pending_tool_calls:
                for tool_call in pending_tool_calls:
                    result = await context.repl.tool_registry.execute(
                        tool_call.name, tool_call.arguments
                    )
                    context.repl.agent.submit_tool_result(tool_call.id, result.content)
                    all_events.append(AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result))

                await run_and_collect(context.repl.agent.continue_with_tool_results())

        await run_and_collect(context.repl.agent.run(config.prompt))
        json_renderer.render_final_json(all_events)


def _create_headless_context(
    provider: ModelProvider,
    settings: object,
    system_prompt: str,
    environment_block: str,
    auto_approve: bool,
    console,
) -> HeadlessContext:
    """Create shared context for headless mode execution.
    
    Args:
        provider: The model provider to use.
        settings: Application settings.
        system_prompt: System prompt for the agent.
        environment_block: Environment context block.
        auto_approve: Whether to auto-approve tool executions.
        console: Console for output rendering.
    
    Returns:
        HeadlessContext with initialized components.
    """
    # Create themed renderer based on settings (for text output mode)
    theme_manager = ThemeManager()
    theme_name = settings.ui.theme if settings.ui else "dark"

    # Validate theme exists, fall back to default if not
    if theme_name not in theme_manager.list_themes():
        # In headless mode, we don't print warnings to console
        theme_name = "dark"

    theme = theme_manager.get_theme(theme_name)
    output_renderer = OutputRenderer(console=console, theme=theme)
    renderer = UIRenderer(console=console, renderer=output_renderer)

    config = ReplConfig(system_prompt=system_prompt, auto_approve_tools=auto_approve)
    repl = Repl(
        provider=provider,
        console=console,
        config=config,
        settings=settings,
        environment_context=environment_block,
        renderer=renderer,
    )

    # Initialize session management
    project_hash = repl.session_manager.compute_project_hash(Path.cwd())
    session = repl.session_manager.create_session(project_hash)
    repl.set_session(session)

    # Initialize RAG system
    rag_system = initialize_rag(settings.rag, index=False)  # No console output in headless
    if rag_system:
        repl.tool_registry.register(rag_system.search_tool)
        repl.rag_system = rag_system

    return HeadlessContext(
        provider=provider,
        settings=settings,
        system_prompt=system_prompt,
        environment_block=environment_block,
        repl=repl,
        rag_system=rag_system,
    )


def _get_output_strategy(output_format: str, console) -> OutputStrategy:
    """Get the appropriate output strategy for the given format.
    
    Args:
        output_format: The output format string.
        console: Console for output rendering.
    
    Returns:
        An OutputStrategy instance.
    
    Raises:
        ValueError: If the output format is not recognized.
    """
    strategies = {
        "text": TextOutputStrategy,
        "json": JsonOutputStrategy,
        "stream-json": StreamJsonOutputStrategy,
        "json-complete": CompleteJsonOutputStrategy,
    }
    
    if output_format not in strategies:
        raise ValueError(f"Unsupported output format: {output_format}")
    
    return strategies[output_format](console)


def _run_headless_refactored(
    prompt: str,
    output_format: str,
    plan_mode: bool = False,
    yes: bool = False,
    agent_role: str | None = None,
    console=None,
) -> None:
    """Refactored version of _run_headless function.
    
    Args:
        prompt: The prompt to process.
        output_format: Output format (text, json, stream-json, json-complete).
        plan_mode: Whether to run in plan mode.
        yes: Auto-approve all tool executions.
        agent_role: Target a specific specialist agent.
        console: Console for output rendering.
    """
    import anyio
    
    provider = _get_provider()
    settings = load_settings()

    # Load context from HENCHMAN.md files
    context_loader = ContextLoader()
    system_prompt = context_loader.load()

    # Gather environment context once
    env_ctx = gather_environment()
    env_block = format_environment_block(env_ctx)

    # Add plan mode prompt if requested
    if plan_mode:  # pragma: no cover
        from henchman.cli.commands.plan import PLAN_MODE_PROMPT
        system_prompt += PLAN_MODE_PROMPT

    # Create shared context
    context = _create_headless_context(
        provider=provider,
        settings=settings,
        system_prompt=system_prompt,
        environment_block=env_block,
        auto_approve=yes,
        console=console,
    )

    # Set plan mode if requested
    if plan_mode and context.repl.session_manager.current:  # pragma: no cover
        context.repl.session_manager.current.plan_mode = True
        context.repl.tool_manager.set_plan_mode(True)

    # Create configuration
    config = HeadlessConfig(
        prompt=prompt,
        output_format=output_format,
        plan_mode=plan_mode,
        auto_approve=yes,
        agent_role=agent_role,
    )

    # Get and execute the appropriate strategy
    strategy = _get_output_strategy(output_format, console)
    
    async def execute_strategy() -> None:
        await strategy.run(context, config)
    
    anyio.run(execute_strategy)