"""Incremental refactoring of _run_headless function."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import anyio
from rich.console import Console

from henchman.cli.console import OutputRenderer, ThemeManager
from henchman.cli.json_output import JsonOutputRenderer
from henchman.cli.repl import Repl, ReplConfig
from henchman.cli.ui_renderer import UIRenderer
from henchman.config import ContextLoader, load_settings
from henchman.config.environment import format_environment_block, gather_environment
from henchman.core.events import AgentEvent, EventType
from henchman.rag import initialize_rag


@dataclass
class HeadlessContext:
    """Shared context for headless mode execution."""
    provider: object
    settings: object
    system_prompt: str
    environment_block: str
    repl: Repl
    rag_system: object | None = None


def _create_headless_context(
    provider: object,
    settings: object,
    system_prompt: str,
    environment_block: str,
    auto_approve: bool,
    console: Console,
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


async def _execute_tool_calls(
    repl: Repl,
    pending_tool_calls: list,
    json_renderer: JsonOutputRenderer | None = None,
    collect_events: list[AgentEvent] | None = None,
    stream_json: bool = False,
) -> None:
    """Execute pending tool calls and handle results.
    
    Args:
        repl: The REPL instance.
        pending_tool_calls: List of tool calls to execute.
        json_renderer: JSON renderer for JSON output modes.
        collect_events: List to collect events for complete JSON mode.
        stream_json: Whether to use streaming JSON rendering.
    """
    for tool_call in pending_tool_calls:
        result = await repl.tool_registry.execute(tool_call.name, tool_call.arguments)
        repl.agent.submit_tool_result(tool_call.id, result.content)
        
        if json_renderer:
            event = AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result)
            if stream_json:
                json_renderer.render_stream_json(event)
            else:
                json_renderer.render(event)
        
        if collect_events is not None:
            collect_events.append(AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result))


async def _process_agent_stream(
    repl: Repl,
    prompt: str,
    agent_role: str | None = None,
    json_renderer: JsonOutputRenderer | None = None,
    collect_events: list[AgentEvent] | None = None,
    stream_json: bool = False,
) -> None:
    """Process agent stream with optional JSON rendering.
    
    Args:
        repl: The REPL instance.
        prompt: The prompt to process.
        agent_role: Optional agent role for direct execution.
        json_renderer: JSON renderer for JSON output modes.
        collect_events: List to collect events for complete JSON mode.
        stream_json: Whether to use streaming JSON rendering.
    """
    # Initialize MCP servers
    await repl.initialize_mcp()

    if repl.rag_system:
        asyncio.create_task(repl.rag_system.index_async())  # type: ignore[attr-defined]

    if agent_role:
        # For text mode with agent role
        await repl._run_agent_direct(agent_role, prompt)
        return

    async def process_stream(stream: AsyncIterator[AgentEvent]) -> None:
        """Process a stream of agent events."""
        pending_tool_calls = []
        async for event in stream:
            if json_renderer:
                if stream_json:
                    json_renderer.render_stream_json(event)
                else:
                    json_renderer.render(event)
            
            if collect_events is not None:
                collect_events.append(event)
            
            if event.type == EventType.TOOL_CALL_REQUEST:
                pending_tool_calls.append(event.data)

        if pending_tool_calls:
            await _execute_tool_calls(
                repl, pending_tool_calls, json_renderer, collect_events, stream_json
            )
            # Continue with tool results
            await process_stream(repl.agent.continue_with_tool_results())

    await process_stream(repl.agent.run(prompt))


def _run_headless_refactored(
    prompt: str,
    output_format: str,
    plan_mode: bool = False,
    yes: bool = False,
    agent_role: str | None = None,
    console: Console | None = None,
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
    from henchman.cli.app import _get_provider
    
    if console is None:
        console = Console()
    
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

    async def run_text_mode() -> None:
        """Run in text output mode."""
        await _process_agent_stream(context.repl, prompt, agent_role)

    async def run_json_mode() -> None:
        """Run in JSON output mode."""
        json_renderer = JsonOutputRenderer(console)
        await _process_agent_stream(
            context.repl, prompt, agent_role, json_renderer, stream_json=False
        )

    async def run_stream_json_mode() -> None:
        """Run in streaming JSON output mode."""
        json_renderer = JsonOutputRenderer(console)
        await _process_agent_stream(
            context.repl, prompt, agent_role, json_renderer, stream_json=True
        )

    async def run_complete_json_mode() -> None:
        """Run in complete JSON output mode."""
        json_renderer = JsonOutputRenderer(console)
        all_events: list[AgentEvent] = []
        await _process_agent_stream(
            context.repl, prompt, agent_role, json_renderer, all_events, stream_json=False
        )
        json_renderer.render_final_json(all_events)

    # Map output format to handler
    handlers = {
        "text": run_text_mode,
        "json": run_json_mode,
        "stream-json": run_stream_json_mode,
        "json-complete": run_complete_json_mode,
    }

    if output_format not in handlers:
        # This should not happen due to Click validation, but handle gracefully
        console.print(f"[red]Error:[/] Unsupported output format: {output_format}")
        return

    anyio.run(handlers[output_format])