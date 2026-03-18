"""HENCHMAN CLI application entry point."""

from __future__ import annotations

import asyncio
import builtins
import logging
import os
import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
import click
from rich.console import Console

from henchman.cli.json_output import JsonOutputRenderer
from henchman.cli.chat_serve import chat_serve_command
from henchman.cli.serve import serve_command
from henchman.core.events import AgentEvent, EventType
from henchman.version import VERSION

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from henchman.providers.base import ModelProvider


_MAX_TEAM_TOOLS_DISPLAY = 5

console = Console()
logger = logging.getLogger(__name__)


def _import_attr(module_path: str, attr_name: str) -> Any:
    """Import a single attribute lazily from *module_path*."""
    module = import_module(module_path)
    return getattr(module, attr_name)


def _import_attrs(module_path: str, *attr_names: str) -> tuple[Any, ...]:
    """Import multiple attributes lazily from *module_path*."""
    module = import_module(module_path)
    return tuple(getattr(module, attr_name) for attr_name in attr_names)


def _get_plan_mode_prompt() -> str:
    """Load the plan-mode prompt lazily to avoid optional import overhead."""
    return _import_attr("henchman.cli.commands.plan", "PLAN_MODE_PROMPT")


@dataclass
class RunConfig:
    """Configuration for running the Henchman CLI."""

    output_format: str = "text"
    plan_mode: bool = False
    yes: bool = False
    agent_role: str | None = None
    prompt: str | None = None
    debug: bool = False
    tui: bool = False
    team: bool = False


@dataclass
class RuntimeContext:
    """Consolidated runtime context for the CLI."""

    provider: Any
    settings: Any
    system_prompt: str
    env_block: str


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

    msg = "No API key configured. Set DEEPSEEK_API_KEY or configure in ~/.henchman/settings.yaml"
    raise click.ClickException(  # pragma: no cover
        msg,
    )


def _get_provider_from_environment() -> ModelProvider | None:
    """Get provider from environment variables.

    Returns:
        ModelProvider instance if environment provides configuration, None otherwise.
    """
    deep_seek_provider = _import_attr("henchman.providers", "DeepSeekProvider")
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("HENCHMAN_API_KEY")
    if api_key:
        return deep_seek_provider(api_key=api_key)
    return None


def _get_provider_from_settings() -> ModelProvider | None:
    """Get provider from settings configuration.

    Returns:
        ModelProvider instance if settings provide configuration, None otherwise.
    """
    try:
        get_default_registry = _import_attr("henchman.providers", "get_default_registry")
        load_settings = _import_attr("henchman.config", "load_settings")
        settings = load_settings()
        registry = get_default_registry()

        provider_name = settings.providers.default or "deepseek"
        provider_settings = getattr(settings.providers, provider_name, {})

        if not isinstance(provider_settings, dict):
            return None

        kwargs = provider_settings.copy()
        _ensure_api_key_in_kwargs(provider_name, kwargs)

        return registry.create(provider_name, **kwargs)
    except Exception:  # pragma: no cover  # noqa: BLE001
        logger.debug("Failed to load provider from settings", exc_info=True)
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
    get_api_key_for_provider = _import_attr(
        "henchman.providers.utils",
        "get_api_key_for_provider",
    )
    api_key = get_api_key_for_provider(provider_name)
    if api_key:
        kwargs["api_key"] = api_key


def _show_team_info() -> None:
    """Display information about the agent team and exit."""
    table_class = _import_attr("rich.table", "Table")
    get_default_team = _import_attr("henchman.agents.presets", "get_default_team")
    table = table_class(title="Henchman Team Roster")
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
            ", ".join(config.tools[:_MAX_TEAM_TOOLS_DISPLAY])
            + ("..." if len(config.tools) > _MAX_TEAM_TOOLS_DISPLAY else ""),
        )

    console.print(table)


def _prepare_runtime_context() -> RuntimeContext:
    """Prepare common runtime objects like provider, settings, and context.

    Returns:
        A RuntimeContext instance.
    """
    context_loader_class, load_settings = _import_attrs(
        "henchman.config",
        "ContextLoader",
        "load_settings",
    )
    format_environment_block, gather_environment = _import_attrs(
        "henchman.config.environment",
        "format_environment_block",
        "gather_environment",
    )
    provider = _get_provider()
    settings = load_settings()

    # Load context from HENCHMAN.md files
    context_loader = context_loader_class()
    system_prompt = context_loader.load()

    # Gather environment context once
    env_ctx = gather_environment()
    env_block = format_environment_block(env_ctx)

    return RuntimeContext(
        provider=provider,
        settings=settings,
        system_prompt=system_prompt,
        env_block=env_block,
    )


def _get_theme_and_renderer(settings: Any, *, silent: bool = False) -> tuple[Any, Any]:
    """Initialize theme and UI renderer based on settings.

    Args:
        settings: Application settings.
        silent: Whether to suppress warnings about missing themes.

    Returns:
        Tuple of (theme, renderer).
    """
    output_renderer_class, theme_manager_class = _import_attrs(
        "henchman.cli.console",
        "OutputRenderer",
        "ThemeManager",
    )
    ui_renderer_class = _import_attr("henchman.cli.ui_renderer", "UIRenderer")
    # Create themed renderer based on settings
    theme_manager = theme_manager_class()
    theme_name = settings.ui.theme if settings.ui else "dark"

    # Validate theme exists, fall back to default if not
    if theme_name not in theme_manager.list_themes():
        if not silent:
            console.print(f"[yellow]Warning:[/] Theme '{theme_name}' not found")
            console.print("[dim]Falling back to default theme (dark)[/]")
        theme_name = "dark"

    theme = theme_manager.get_theme(theme_name)
    output_renderer = output_renderer_class(console=console, theme=theme)
    renderer = ui_renderer_class(console=console, renderer=output_renderer)

    return theme, renderer


def _build_repl_instance(ctx: RuntimeContext, config: RunConfig, renderer: Any) -> Any:
    """Create a configured Repl instance from context and config.

    Args:
        ctx: The runtime context containing provider and settings.
        config: Run configuration.
        renderer: The UI renderer instance.

    Returns:
        Configured Repl instance.
    """
    repl_class, repl_config_class = _import_attrs(
        "henchman.cli.repl",
        "Repl",
        "ReplConfig",
    )
    repl_config = repl_config_class(
        system_prompt=ctx.system_prompt,
        auto_approve_tools=config.yes,
    )
    return repl_class(
        provider=ctx.provider,
        console=console,
        config=repl_config,
        settings=ctx.settings,
        environment_context=ctx.env_block,
        renderer=renderer,
    )


def _setup_repl_session(repl: Any) -> None:
    """Initialize session management for the REPL.

    Args:
        repl: The REPL instance.
    """
    project_hash = repl.session_manager.compute_project_hash(Path.cwd())
    session = repl.session_manager.create_session(project_hash)
    repl.set_session(session)


def _setup_repl_rag(repl: Any, settings: Any, *, headless: bool = False) -> None:
    """Initialize the RAG system for the REPL.

    Args:
        repl: The REPL instance.
        settings: Application settings.
        headless: If True, suppresses console output during RAG initialisation.
    """
    initialize_rag = _import_attr("henchman.rag", "initialize_rag")
    if headless:
        rag_system = initialize_rag(settings.rag, index=False)
    else:
        rag_system = initialize_rag(settings.rag, console=console, index=False)
    if rag_system:
        repl.tool_registry.register(rag_system.search_tool)
        repl.rag_system = rag_system


def _apply_interactive_plan_mode(repl: Any, config: RunConfig) -> None:
    """Apply plan mode settings to an interactive REPL, including the agent prompt.

    Args:
        repl: The REPL instance.
        config: Run configuration.
    """
    if not config.plan_mode or not repl.session_manager.current:
        return
    repl.session_manager.current.plan_mode = True
    repl.tool_manager.set_plan_mode(plan_mode=True)
    repl.agent.system_prompt += _get_plan_mode_prompt()


def _dispatch_interactive_run(repl: Any, config: RunConfig) -> None:
    """Run the interactive REPL, dispatching on output format.

    Args:
        repl: The REPL instance.
        config: Run configuration.
    """
    if config.output_format == "text":
        if config.agent_role:

            async def start_repl() -> None:
                """Start the REPL with agent role context."""
                await repl.run()

            anyio.run(start_repl)
        else:
            anyio.run(repl.run)
    else:  # pragma: no cover
        console.print(
            "[yellow]Warning: JSON output formats not supported in interactive mode. "
            "Using text format.[/yellow]",
        )
        anyio.run(repl.run)


def _run_interactive(config: RunConfig) -> None:
    """Run interactive REPL mode.

    Args:
        config: Run configuration.
    """
    ctx = _prepare_runtime_context()
    _, renderer = _get_theme_and_renderer(ctx.settings)
    repl = _build_repl_instance(ctx, config, renderer)
    _setup_repl_session(repl)
    _setup_repl_rag(repl, ctx.settings)
    _apply_interactive_plan_mode(repl, config)
    _dispatch_interactive_run(repl, config)


def _run_textual_tui(config: RunConfig) -> None:
    """Run Textual TUI mode.

    Args:
        config: Run configuration.
    """
    textual_config_class, run_textual_app = _import_attrs(
        "henchman.cli.textual_app",
        "TextualConfig",
        "run_textual_app",
    )
    ctx = _prepare_runtime_context()

    # Add plan mode prompt if requested
    if config.plan_mode:
        ctx.system_prompt += _get_plan_mode_prompt()

    textual_config = textual_config_class(
        system_prompt=ctx.system_prompt,
        auto_approve_tools=config.yes,
        agent_role=config.agent_role,
    )

    if config.output_format != "text":
        console.print(
            "[yellow]Warning:[/] Textual TUI only supports text output format. Using text format.",
        )

    run_textual_app(
        provider=ctx.provider,
        config=textual_config,
        settings=ctx.settings,
        environment_context=ctx.env_block,
    )


def _create_headless_repl(config: RunConfig) -> tuple[Any, Any, Any]:
    """Create and configure a REPL instance for headless mode.

    Args:
        config: Run configuration.

    Returns:
        Tuple of (repl instance, settings, system_prompt).
    """
    ctx = _prepare_runtime_context()

    # Add plan mode prompt before building the Repl so it is baked in
    if config.plan_mode:  # pragma: no cover
        ctx.system_prompt += _get_plan_mode_prompt()

    _, renderer = _get_theme_and_renderer(ctx.settings, silent=True)
    repl = _build_repl_instance(ctx, config, renderer)
    _setup_repl_session(repl)
    _setup_repl_rag(repl, ctx.settings, headless=True)

    # Set plan mode on session/tool-manager if requested
    if config.plan_mode and repl.session_manager.current:  # pragma: no cover
        repl.session_manager.current.plan_mode = True
        repl.tool_manager.set_plan_mode(plan_mode=True)

    return repl, ctx.settings, ctx.system_prompt


def _dispatch_headless_format(repl: Any, config: RunConfig) -> None:
    """Dispatch to the appropriate headless runner based on output format.

    Args:
        repl: The REPL instance.
        config: Run configuration.
    """
    prompt = config.prompt
    if config.output_format == "text":
        anyio.run(_run_headless_text, repl, prompt, config.agent_role)
        return
    if config.output_format == "json":
        anyio.run(_run_headless_json_format, repl, prompt, "json")
    elif config.output_format == "stream-json":
        anyio.run(_run_headless_json_format, repl, prompt, "stream-json")
    elif config.output_format == "json-complete":  # pragma: no branch
        anyio.run(_run_headless_json_complete, repl, prompt)


def _run_headless(config: RunConfig) -> None:
    """Run headless mode with a single prompt.

    Args:
        config: Run configuration.
    """
    if config.prompt is None:
        return

    repl, _, _ = _create_headless_repl(config)
    _dispatch_headless_format(repl, config)
    _check_completion_status(repl)


async def _run_headless_text(
    repl: Any,
    prompt: str,
    agent_role: str | None = None,
) -> None:
    """Process a single prompt and exit with text output.

    Args:
        repl: The REPL instance.
        prompt: The prompt to process.
        agent_role: Target a specific specialist agent.
    """
    # Initialize MCP servers
    await repl.initialize_mcp()

    _start_rag_indexing(repl)

    if agent_role:
        run_agent_direct = object.__getattribute__(repl, "_run_agent_direct")
        await run_agent_direct(agent_role, prompt)
    else:
        await repl.process_input(prompt)


async def _initialize_json_processing(repl: Any) -> JsonOutputRenderer:
    """Initialize MCP servers and RAG system for JSON processing.

    Args:
        repl: The REPL instance.

    Returns:
        JsonOutputRenderer instance.
    """
    # Initialize MCP servers
    await repl.initialize_mcp()

    _start_rag_indexing(repl)

    return JsonOutputRenderer(console)


def _start_rag_indexing(repl: Any) -> None:
    """Start asynchronous RAG indexing while retaining the created task."""
    rag_system = getattr(repl, "rag_system", None)
    if rag_system:
        object.__setattr__(
            repl,
            "_rag_index_task",
            asyncio.create_task(rag_system.index_async()),
        )


async def _process_tool_calls(
    repl: Any,
    pending_tool_calls: list[Any],
    render_func: Callable[[AgentEvent], None],
    collect_events: list[Any] | None = None,
) -> None:
    """Execute pending tool calls and handle results.

    Args:
        repl: The REPL instance.
        pending_tool_calls: List of tool call requests.
        render_func: Function to render events.
        collect_events: Optional list to collect events (for json-complete mode).
    """
    for tool_call in pending_tool_calls:
        result = await repl.tool_registry.execute(tool_call.name, tool_call.arguments)
        repl.agent.submit_tool_result(tool_call.id, result.content)

        if collect_events is not None:
            collect_events.append(
                AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result),
            )
        else:
            render_func(
                AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result),
            )


async def _run_headless_json_mode(
    repl: Any,
    prompt: str,
    render_event: Callable[[AgentEvent], None],
) -> None:
    """Process an agent stream using the provided render function.

    Args:
        repl: The REPL instance.
        prompt: The prompt to process.
        render_event: Function used to render each AgentEvent.
    """

    async def run_and_render(stream: AsyncIterator[AgentEvent]) -> None:
        """Run the agent stream and render events."""
        pending_tool_calls: list[Any] = []
        async for event in stream:
            render_event(event)
            if event.type == EventType.TOOL_CALL_REQUEST:
                pending_tool_calls.append(event.data)

        if pending_tool_calls:
            await _process_tool_calls(repl, pending_tool_calls, render_event)
            await run_and_render(repl.agent.continue_with_tool_results())

    await run_and_render(repl.agent.run(prompt))


async def _run_headless_json_format(
    repl: Any,
    prompt: str,
    render_mode: str,
) -> None:
    """Process a single prompt and exit with JSON output.

    Args:
        repl: The REPL instance.
        prompt: The prompt to process.
        render_mode: Either "stream-json" (line-delimited) or "json" (batch).
    """
    json_renderer = await _initialize_json_processing(repl)
    render_fn = (
        json_renderer.render_stream_json
        if render_mode == "stream-json"
        else json_renderer.render
    )
    await _run_headless_json_mode(repl, prompt, render_fn)


async def _run_headless_json_complete(
    repl: Any,
    prompt: str,
) -> None:
    """Process a single prompt and exit with complete JSON output.

    Args:
        repl: The REPL instance.
        prompt: The prompt to process.
    """

    json_renderer = await _initialize_json_processing(repl)
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
            await _process_tool_calls(
                repl,
                pending_tool_calls,
                lambda _: None,  # No rendering during collection
                collect_events=all_events,
            )
            await run_and_collect(repl.agent.continue_with_tool_results())

    await run_and_collect(repl.agent.run(prompt))
    json_renderer.render_final_json(all_events)


def _check_completion_status(repl: Any) -> None:
    """Check if agent completed without work and exit with appropriate code.

    Args:
        repl: The REPL instance.
    """
    completion_status = _import_attr(
        "henchman.agents.orchestrator",
        "CompletionStatus",
    )
    if (
        hasattr(repl, "orchestrator")
        and repl.orchestrator.last_completion_status == completion_status.NO_WORK_DONE
    ):
        sys.exit(2)


@click.group(name="henchman", invoke_without_command=True)
@click.version_option(version=VERSION, prog_name="henchman")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Henchman-AI: A model-agnostic AI agent CLI.

    Start an interactive session, run with --prompt for headless mode,
    or start an API server with the serve command.

    Args:
        ctx (click.Context): The Click context object.

    Returns:
        None: This function doesn't return anything.
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
def chat_command(**kwargs: Any) -> None:
    """Start an interactive chat session or run with --prompt for headless mode.

    Args:
        **kwargs: Click option values forwarded from the CLI decorators.
            Recognised keys: prompt, agent, team, output_format, plan, yes,
            tui, debug.

    Returns:
        None
    """
    config = RunConfig(
        prompt=kwargs.get("prompt"),
        agent_role=kwargs.get("agent"),
        team=kwargs.get("team", False),
        output_format=kwargs.get("output_format", "text"),
        plan_mode=kwargs.get("plan", False),
        yes=kwargs.get("yes", False),
        tui=kwargs.get("tui", False),
        debug=kwargs.get("debug", False),
    )
    _execute_chat_command(config)


def _execute_chat_command(config: RunConfig) -> None:
    """Execute the chat command given a fully-constructed RunConfig.

    Separates Click adapter concerns from the actual command logic so that
    tests and other callers can drive behavior via ``RunConfig`` directly.

    Args:
        config: Fully-populated run configuration.
    """
    # Configure debug output filtering
    if not config.debug:
        _orig_print = builtins.print

        def _filtered_print(*args: object, **kwargs: object) -> None:
            """Filter out DEBUG print statements when debug mode is disabled."""
            if args and isinstance(args[0], str) and args[0].startswith("DEBUG"):
                return
            _orig_print(*args, **kwargs)  # type: ignore[call-overload]

        builtins.print = _filtered_print

    if config.team:
        _show_team_info()
        return

    if config.tui and config.prompt:
        console.print(
            (
                "[yellow]Warning:[/] Textual TUI does not support headless mode. "
                "Using interactive mode."
            ),
        )
        config.prompt = None

    if config.prompt:
        _run_headless(config)
    elif config.tui:
        _run_textual_tui(config)
    else:
        _run_interactive(config)


# Add serve command to CLI group
cli.add_command(serve_command)
cli.add_command(chat_serve_command)


def main() -> None:  # pragma: no cover
    """Main entry point for the CLI.

    Returns:
        None
    """
    # If Textual is inspecting this via `textual run`, return the App directly.
    # This prevents Textual from calling the Click `cli` command which crashes.
    if "textual" in sys.argv[0] and "run" in sys.argv:
        # Lazy import to avoid loading Textual for REPL mode
        app_class = _import_attr("henchman.cli.textual_app", "HenchmanTextualApp")
        app_class().run()
        return

    # For backward compatibility, if no subcommand is specified,
    # assume the user wants to run chat with the old-style arguments
    if len(sys.argv) == 1 or (
        len(sys.argv) > 1
        and not sys.argv[1].startswith("-")
        and sys.argv[1] not in ["chat", "serve"]
    ):
        # Insert "chat" as the subcommand
        sys.argv.insert(1, "chat")

    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
