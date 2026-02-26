"""HENCHMAN CLI application entry point."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import TYPE_CHECKING

import anyio
import click
from rich.console import Console

from henchman.cli.serve import serve_command
from henchman.version import VERSION

if TYPE_CHECKING:
    from henchman.providers.base import ModelProvider


def __getattr__(name: str) -> object:
    """Lazy import for Textual dev mode (``textual run henchman``)."""
    if name == "app":
        from henchman.cli.textual_app import HenchmanTextualApp

        return HenchmanTextualApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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

        logging.getLogger(__name__).debug("Failed to load provider from settings", exc_info=True)
        return None


def _ensure_api_key_in_kwargs(provider_name: str, kwargs: dict[str, object]) -> None:
    """Ensure api_key is present in kwargs, falling back to environment variables.

    Args:
        provider_name: Name of the provider (e.g., "deepseek", "anthropic").
        kwargs: Provider configuration dictionary to modify.
    """
    if kwargs.get("api_key"):
        return

    # Get the appropriate environment variable for this provider
    from henchman.providers.utils import get_api_key_for_provider

    api_key = get_api_key_for_provider(provider_name)
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
        table.add_row(
            role,
            config.description,
            ", ".join(config.tools[:5]) + ("..." if len(config.tools) > 5 else ""),
        )

    console.print(table)


def _run_interactive(
    output_format: str, plan_mode: bool = False, yes: bool = False, agent_role: str | None = None
) -> None:
    """Run interactive REPL mode.

    Args:
        output_format: Output format (text, json, stream-json, json-complete).
        plan_mode: Whether to start in plan mode.
        yes: Auto-approve all tool executions.
        agent_role: Target a specific specialist agent.
    """
    from pathlib import Path

    from henchman.cli.console import OutputRenderer, ThemeManager
    from henchman.cli.repl import Repl, ReplConfig
    from henchman.cli.ui_renderer import UIRenderer
    from henchman.config import ContextLoader, load_settings
    from henchman.config.environment import format_environment_block, gather_environment
    from henchman.rag import initialize_rag

    provider = _get_provider()
    settings = load_settings()

    # Load context from HENCHMAN.md files
    context_loader = ContextLoader()
    system_prompt = context_loader.load()

    # Gather environment context once
    env_ctx = gather_environment()
    env_block = format_environment_block(env_ctx)

    # Create themed renderer based on settings
    theme_manager = ThemeManager()
    theme_name = settings.ui.theme if settings.ui else "dark"

    # Validate theme exists, fall back to default if not
    if theme_name not in theme_manager.list_themes():
        console.print(f"[yellow]Warning:[/] Theme '{theme_name}' not found")
        console.print("[dim]Falling back to default theme (dark)[/]")
        theme_name = "dark"

    theme = theme_manager.get_theme(theme_name)
    output_renderer = OutputRenderer(console=console, theme=theme)
    renderer = UIRenderer(console=console, renderer=output_renderer)

    config = ReplConfig(system_prompt=system_prompt, auto_approve_tools=yes)
    repl = Repl(
        provider=provider,
        console=console,
        config=config,
        settings=settings,
        environment_context=env_block,
        renderer=renderer,
    )

    # Initialize session management
    project_hash = repl.session_manager.compute_project_hash(Path.cwd())
    session = repl.session_manager.create_session(project_hash)
    repl.set_session(session)

    # Initialize RAG system
    rag_system = initialize_rag(settings.rag, console=console, index=False)
    if rag_system:
        repl.tool_registry.register(rag_system.search_tool)
        repl.rag_system = rag_system

    # Set plan mode if requested
    if plan_mode and repl.session_manager.current:
        repl.session_manager.current.plan_mode = True
        repl.tool_manager.set_plan_mode(True)
        # Add plan mode prompt to system prompt
        from henchman.cli.commands.plan import PLAN_MODE_PROMPT

        repl.agent.system_prompt += PLAN_MODE_PROMPT

    if output_format == "text":
        if agent_role:

            async def start_repl() -> None:
                """Start the REPL with agent role context.

                This wrapper function allows passing agent_role context
                to the REPL in future implementations.
                """
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


def _run_textual_tui(
    output_format: str, plan_mode: bool = False, yes: bool = False, agent_role: str | None = None
) -> None:
    """Run Textual TUI mode.

    Args:
        output_format: Output format (ignored for TUI mode).
        plan_mode: Whether to start in plan mode.
        yes: Auto-approve all tool executions.
        agent_role: Target a specific specialist agent.
    """
    from henchman.cli.textual_app import TextualConfig, run_textual_app
    from henchman.config import ContextLoader, load_settings
    from henchman.config.environment import format_environment_block, gather_environment

    provider = _get_provider()
    settings = load_settings()

    # Load context from HENCHMAN.md files
    context_loader = ContextLoader()
    system_prompt = context_loader.load()

    # Gather environment context once
    env_ctx = gather_environment()
    env_block = format_environment_block(env_ctx)

    # Add plan mode prompt if requested
    if plan_mode:
        from henchman.cli.commands.plan import PLAN_MODE_PROMPT

        system_prompt += PLAN_MODE_PROMPT

    config = TextualConfig(system_prompt=system_prompt, auto_approve_tools=yes, agent_role=agent_role)

    if output_format != "text":
        console.print(
            "[yellow]Warning:[/] Textual TUI only supports text output format. Using text format."
        )

    run_textual_app(
        provider=provider,
        config=config,
        settings=settings,
        environment_context=env_block,
    )


def _run_headless(
    prompt: str,
    output_format: str,
    plan_mode: bool = False,
    yes: bool = False,
    agent_role: str | None = None,
) -> None:
    """Run headless mode with a single prompt.

    Args:
        prompt: The prompt to process.
        output_format: Output format (text, json, stream-json, json-complete).
        plan_mode: Whether to run in plan mode.
        yes: Auto-approve all tool executions.
        agent_role: Target a specific specialist agent.
    """
    from pathlib import Path

    from henchman.cli.console import OutputRenderer, ThemeManager
    from henchman.cli.json_output import JsonOutputRenderer
    from henchman.cli.repl import Repl, ReplConfig
    from henchman.cli.ui_renderer import UIRenderer
    from henchman.config import ContextLoader, load_settings
    from henchman.config.environment import format_environment_block, gather_environment
    from henchman.core.events import EventType
    from henchman.rag import initialize_rag

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

    config = ReplConfig(system_prompt=system_prompt, auto_approve_tools=yes)
    repl = Repl(
        provider=provider,
        console=console,
        config=config,
        settings=settings,
        environment_context=env_block,
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

    # Set plan mode if requested
    if plan_mode and repl.session_manager.current:  # pragma: no cover
        repl.session_manager.current.plan_mode = True
        repl.tool_manager.set_plan_mode(True)

    async def run_single_prompt_text() -> None:  # pragma: no cover
        """Process a single prompt and exit with text output."""
        # Initialize MCP servers
        await repl.initialize_mcp()

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

        # Initialize MCP servers
        await repl.initialize_mcp()

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

        # Initialize MCP servers
        await repl.initialize_mcp()

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

        # Initialize MCP servers
        await repl.initialize_mcp()

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

    # Exit with code 2 if the agent completed without doing any work.
    # This enables automation scripts to detect and handle the case
    # where the LLM narrated intent but never executed any tool calls.
    from henchman.agents.orchestrator import CompletionStatus

    if (
        hasattr(repl, "orchestrator")
        and repl.orchestrator.last_completion_status == CompletionStatus.NO_WORK_DONE
    ):
        sys.exit(2)


@click.group(name="henchman", invoke_without_command=True)
@click.version_option(version=VERSION, prog_name="henchman")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Henchman-AI: A model-agnostic AI agent CLI.

    Start an interactive session, run with --prompt for headless mode,
    or start an API server with the serve command.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command(name="chat")
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
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug output",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    help="Auto-approve all tool executions (non-interactive mode)",
)
@click.option(
    "--tui",
    is_flag=True,
    default=False,
    help="Use Textual TUI interface (experimental)",
)
def chat_command(
    prompt: str | None,
    agent: str | None,
    team: bool,
    output_format: str,
    plan: bool,
    yes: bool,
    tui: bool,
    debug: bool,
) -> None:
    """Start an interactive chat session or run with --prompt for headless mode."""
    # Configure debug output filtering
    if not debug:
        import builtins
        _orig_print = builtins.print
        def _filtered_print(*args: object, **kwargs: object) -> None:
            """Filter out DEBUG print statements when debug mode is disabled.

            Args:
                *args: Arguments passed to print function.
                **kwargs: Keyword arguments passed to print function.
            """
            if args and isinstance(args[0], str) and args[0].startswith("DEBUG"):
                return
            _orig_print(*args, **kwargs)  # type: ignore[call-overload]
        builtins.print = _filtered_print
    if team:
        _show_team_info()
        return

    if tui and prompt:
        console.print(
            "[yellow]Warning:[/] Textual TUI does not support headless mode. Using interactive mode."
        )
        tui = True
        prompt = None

    if prompt:
        _run_headless(prompt, output_format, plan, yes, agent_role=agent)
    elif tui:
        _run_textual_tui(output_format, plan, yes, agent_role=agent)
    else:
        _run_interactive(output_format, plan, yes, agent_role=agent)


# Add serve command to CLI group
cli.add_command(serve_command)


def main() -> None:  # pragma: no cover
    """Main entry point for the CLI."""
    import sys

    # If Textual is inspecting this via `textual run`, return the App directly.
    # This prevents Textual from calling the Click `cli` command which crashes.
    if "textual" in sys.argv[0] and "run" in sys.argv:
        # Lazy import to avoid loading Textual for REPL mode
        from henchman.cli.textual_app import HenchmanTextualApp
        HenchmanTextualApp().run()
        return

    # For backward compatibility, if no subcommand is specified,
    # assume the user wants to run chat with the old-style arguments
    if len(sys.argv) == 1 or (
        len(sys.argv) > 1 and
        not sys.argv[1].startswith("-") and
        sys.argv[1] not in ["chat", "serve"]
    ):
        # Insert "chat" as the subcommand
        sys.argv.insert(1, "chat")

    cli()



if __name__ == "__main__":  # pragma: no cover
    main()
