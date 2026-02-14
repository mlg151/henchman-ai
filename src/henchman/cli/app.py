"""MLG CLI application entry point."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import anyio
import click
from rich.console import Console

from henchman.version import VERSION

if TYPE_CHECKING:
    from henchman.providers.base import ModelProvider

console = Console()


def _get_provider() -> ModelProvider:
    """Get the configured model provider.

    Returns:
        A ModelProvider instance.

    Raises:
        click.ClickException: If no provider is configured.
    """
    # Try to get provider from environment first
    provider_from_env = _get_provider_from_environment()
    if provider_from_env:
        return provider_from_env

    # Try to get provider from settings
    provider_from_settings = _get_provider_from_settings()
    if provider_from_settings:
        return provider_from_settings

    raise click.ClickException(  # pragma: no cover
        "No API key configured. Set DEEPSEEK_API_KEY or configure in ~/.henchman/settings.yaml"
    )


def _get_provider_from_environment() -> ModelProvider | None:
    """Get provider from environment variables.

    Returns:
        ModelProvider instance if environment provides configuration, None otherwise.
    """
    from henchman.providers import DeepSeekProvider

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("HENCHMAN_API_KEY")
    if api_key:
        return DeepSeekProvider(api_key=api_key)
    return None


def _get_provider_from_settings() -> ModelProvider | None:
    """Get provider from settings configuration.

    Returns:
        ModelProvider instance if settings provide configuration, None otherwise.
    """
    from henchman.providers import get_default_registry

    try:
        from henchman.config import load_settings

        settings = load_settings()
        registry = get_default_registry()

        provider_name = settings.providers.default or "deepseek"
        provider_settings = getattr(settings.providers, provider_name, {})

        if not isinstance(provider_settings, dict):
            return None

        kwargs = provider_settings.copy()
        _ensure_api_key_in_kwargs(provider_name, kwargs)
        
        return registry.create(provider_name, **kwargs)
    except Exception:  # pragma: no cover
        # Log the error for debugging but don't crash
        import logging
        logging.getLogger(__name__).debug(
            "Failed to load provider from settings", exc_info=True
        )
        return None


def _ensure_api_key_in_kwargs(provider_name: str, kwargs: dict[str, object]) -> None:
    """Ensure api_key is present in kwargs, falling back to environment variables.

    Args:
        provider_name: Name of the provider (e.g., "deepseek", "anthropic").
        kwargs: Provider configuration dictionary to modify.
    """
    if kwargs.get("api_key"):
        return

    if provider_name == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    else:
        api_key = os.environ.get("HENCHMAN_API_KEY")

    if api_key:
        kwargs["api_key"] = api_key


def _show_team_info() -> None:
    """Display information about the agent team and exit."""
    from rich.table import Table

    from henchman.agents.presets import get_default_team

    table = Table(title="Henchman Team Roster")
    table.add_column("Role", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Tools", style="yellow")

    team = get_default_team()
    # Add Tech Lead
    table.add_row("tech_lead", "Team orchestrator and strategist", "all + delegate")

    for role, config in team.items():
        table.add_row(role, config.description, ", ".join(config.tools[:5]) + ("..." if len(config.tools) > 5 else ""))

    console.print(table)


def _run_interactive(
    output_format: str,
    plan_mode: bool = False,
    yes: bool = False,
    agent_role: str | None = None
) -> None:
    """Run interactive REPL mode.

    Args:
        output_format: Output format (text, json, stream-json, json-complete).
        plan_mode: Whether to start in plan mode.
        yes: Auto-approve all tool executions.
    """
    from pathlib import Path

    from henchman.cli.repl import Repl, ReplConfig
    from henchman.config import ContextLoader, load_settings
    from henchman.core.session import SessionManager
    from henchman.rag import initialize_rag

    provider = _get_provider()
    settings = load_settings()

    # Load context from MLG.md files
    context_loader = ContextLoader()
    system_prompt = context_loader.load()

    config = ReplConfig(system_prompt=system_prompt, auto_approve_tools=yes)
    repl = Repl(provider=provider, console=console, config=config, settings=settings)

    # Initialize session management
    session_manager = SessionManager()
    project_hash = session_manager.compute_project_hash(Path.cwd())
    session = session_manager.create_session(project_hash)

    repl.session_manager = session_manager
    repl.session = session

    # Initialize RAG system
    rag_system = initialize_rag(settings.rag, console=console, index=False)
    if rag_system:
        repl.tool_registry.register(rag_system.search_tool)
        repl.rag_system = rag_system

    # Set plan mode if requested
    if plan_mode and repl.session:
        repl.session.plan_mode = True
        repl.tool_manager.set_plan_mode(True)
        # Add plan mode prompt to system prompt
        from henchman.cli.commands.plan import PLAN_MODE_PROMPT

        repl.agent.system_prompt += PLAN_MODE_PROMPT

    if output_format == "text":
        if agent_role:
            async def start_repl() -> None:
                # In the future we might want to do something with agent_role here
                await repl.run()
            anyio.run(start_repl)
        else:
            anyio.run(repl.run)
    else:  # pragma: no cover
        console.print(
            "[yellow]Warning: JSON output formats not supported in interactive mode. "
            "Using text format.[/yellow]"
        )
        anyio.run(repl.run)


def _run_headless(
    prompt: str,
    output_format: str,
    plan_mode: bool = False,
    yes: bool = False,
    agent_role: str | None = None
) -> None:
    """Run headless mode with a single prompt.

    Args:
        prompt: The prompt to process.
        output_format: Output format (text, json, stream-json, json-complete).
        plan_mode: Whether to run in plan mode.
        yes: Auto-approve all tool executions.
    """
    from pathlib import Path

    from henchman.cli.json_output import JsonOutputRenderer
    from henchman.cli.repl import Repl, ReplConfig
    from henchman.config import ContextLoader, load_settings
    from henchman.core.events import EventType
    from henchman.core.session import SessionManager
    from henchman.rag import initialize_rag

    provider = _get_provider()
    settings = load_settings()

    # Load context from MLG.md files
    context_loader = ContextLoader()
    system_prompt = context_loader.load()

    # Add plan mode prompt if requested
    if plan_mode:  # pragma: no cover
        from henchman.cli.commands.plan import PLAN_MODE_PROMPT

        system_prompt += PLAN_MODE_PROMPT

    config = ReplConfig(system_prompt=system_prompt, auto_approve_tools=yes)
    repl = Repl(provider=provider, console=console, config=config, settings=settings)

    # Initialize session management
    session_manager = SessionManager()
    project_hash = session_manager.compute_project_hash(Path.cwd())
    session = session_manager.create_session(project_hash)

    repl.session_manager = session_manager
    repl.session = session

    # Initialize RAG system
    rag_system = initialize_rag(settings.rag, index=False)  # No console output in headless
    if rag_system:
        repl.tool_registry.register(rag_system.search_tool)
        repl.rag_system = rag_system

    # Set plan mode if requested
    if plan_mode and repl.session:  # pragma: no cover
        repl.session.plan_mode = True
        repl.tool_manager.set_plan_mode(True)

    async def run_single_prompt_text() -> None:  # pragma: no cover
        """Process a single prompt and exit with text output."""
        if repl.rag_system:
            asyncio.create_task(repl.rag_system.index_async())  # type: ignore[attr-defined]

        if agent_role:
            await repl._run_agent_direct(agent_role, prompt)
        else:
            await repl.process_input(prompt)

    async def run_single_prompt_json() -> None:
        """Process a single prompt and exit with JSON output."""
        from collections.abc import AsyncIterator

        from henchman.core.events import AgentEvent

        if repl.rag_system:
            asyncio.create_task(repl.rag_system.index_async())  # type: ignore[attr-defined]

        json_renderer = JsonOutputRenderer(console)

        # We need to manually run the tool loop for JSON output
        # to ensure all events are rendered as JSON
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
                    result = await repl.tool_registry.execute(tool_call.name, tool_call.arguments)
                    repl.agent.submit_tool_result(tool_call.id, result.content)
                    # Emit tool result event
                    json_renderer.render(AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result))

                # Continue
                await run_and_render(repl.agent.continue_with_tool_results())

        await run_and_render(repl.agent.run(prompt))

    async def run_single_prompt_stream_json() -> None:
        """Process a single prompt and exit with streaming JSON output."""
        from collections.abc import AsyncIterator

        from henchman.core.events import AgentEvent

        if repl.rag_system:
            asyncio.create_task(repl.rag_system.index_async())  # type: ignore[attr-defined]

        json_renderer = JsonOutputRenderer(console)

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
                    result = await repl.tool_registry.execute(tool_call.name, tool_call.arguments)
                    repl.agent.submit_tool_result(tool_call.id, result.content)
                    json_renderer.render_stream_json(
                        AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result)
                    )

                await run_and_render_stream(repl.agent.continue_with_tool_results())

        await run_and_render_stream(repl.agent.run(prompt))

    async def run_single_prompt_json_complete() -> None:
        """Process a single prompt and exit with complete JSON output."""
        from collections.abc import AsyncIterator

        from henchman.core.events import AgentEvent

        if repl.rag_system:
            asyncio.create_task(repl.rag_system.index_async())  # type: ignore[attr-defined]

        json_renderer = JsonOutputRenderer(console)
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
                    result = await repl.tool_registry.execute(tool_call.name, tool_call.arguments)
                    repl.agent.submit_tool_result(tool_call.id, result.content)
                    all_events.append(AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result))

                await run_and_collect(repl.agent.continue_with_tool_results())

        await run_and_collect(repl.agent.run(prompt))
        json_renderer.render_final_json(all_events)

    if output_format == "text":
        anyio.run(run_single_prompt_text)
    elif output_format == "json":
        anyio.run(run_single_prompt_json)
    elif output_format == "stream-json":
        anyio.run(run_single_prompt_stream_json)
    elif output_format == "json-complete":
        anyio.run(run_single_prompt_json_complete)
    else:  # pragma: no cover
        pass


@click.command()
@click.version_option(version=VERSION, prog_name="henchman")
@click.option("-p", "--prompt", help="Run with a single prompt and exit")
@click.option("-a", "--agent", help="Target a specific specialist agent")
@click.option("--team", is_flag=True, help="Show team information and exit")
@click.option(
    "--output-format",
    type=click.Choice(["text", "json", "stream-json", "json-complete"]),
    default="text",
    help="Output format for responses",
)
@click.option(
    "--plan",
    is_flag=True,
    default=False,
    help="Start in plan mode (read-only)",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    help="Auto-approve all tool executions (non-interactive mode)",
)
def cli(
    prompt: str | None,
    agent: str | None,
    team: bool,
    output_format: str,
    plan: bool,
    yes: bool
) -> None:
    """Henchman-AI: A model-agnostic AI agent CLI.

    Start an interactive session or run with --prompt for headless mode.
    """
    if team:
        _show_team_info()
        return

    if prompt:
        _run_headless(prompt, output_format, plan, yes, agent_role=agent)
    else:
        _run_interactive(output_format, plan, yes, agent_role=agent)


def main() -> None:  # pragma: no cover
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
