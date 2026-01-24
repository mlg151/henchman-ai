"""MLG CLI application entry point."""

from __future__ import annotations

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
    from henchman.providers import DeepSeekProvider, get_default_registry

    # Check environment for API key
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("HENCHMAN_API_KEY")

    if api_key:
        return DeepSeekProvider(api_key=api_key)

    # Try to load from settings
    try:
        from henchman.config import load_settings

        settings = load_settings()
        registry = get_default_registry()

        provider_name = settings.providers.default or "deepseek"
        provider_settings = getattr(settings.providers, provider_name, None)

        if provider_settings:
            return registry.create(
                provider_name,
                api_key=getattr(provider_settings, "api_key", None) or "",
                model=getattr(provider_settings, "model", None),
            )
    except Exception:  # pragma: no cover
        pass

    raise click.ClickException(  # pragma: no cover
        "No API key configured. Set DEEPSEEK_API_KEY or configure in ~/.henchman/settings.yaml"
    )


def _run_interactive(output_format: str, plan_mode: bool = False) -> None:
    """Run interactive REPL mode.

    Args:
        output_format: Output format (text, json, stream-json).
        plan_mode: Whether to start in plan mode.
    """
    from henchman.cli.repl import Repl, ReplConfig
    from henchman.config import ContextLoader, load_settings

    provider = _get_provider()
    settings = load_settings()

    # Load context from MLG.md files
    context_loader = ContextLoader()
    system_prompt = context_loader.load()

    config = ReplConfig(system_prompt=system_prompt)
    repl = Repl(
        provider=provider,
        console=console,
        config=config,
        settings=settings
    )

    # Set plan mode if requested
    if plan_mode and repl.session:
        repl.session.plan_mode = True
        repl.tool_registry.set_plan_mode(True)
        # Add plan mode prompt to system prompt
        from henchman.cli.commands.plan import PLAN_MODE_PROMPT
        repl.agent.system_prompt += PLAN_MODE_PROMPT

    if output_format == "text":
        anyio.run(repl.run)
    else:  # pragma: no cover
        console.print(
            "[yellow]Warning: JSON output formats not supported in interactive mode. "
            "Using text format.[/yellow]"
        )
        anyio.run(repl.run)


def _run_headless(prompt: str, output_format: str, plan_mode: bool = False) -> None:
    """Run headless mode with a single prompt.

    Args:
        prompt: The prompt to process.
        output_format: Output format (text, json, stream-json).
        plan_mode: Whether to run in plan mode.
    """
    from henchman.cli.json_output import JsonOutputRenderer
    from henchman.cli.repl import Repl, ReplConfig
    from henchman.config import ContextLoader
    from henchman.core.events import EventType

    provider = _get_provider()

    # Load context from MLG.md files
    context_loader = ContextLoader()
    system_prompt = context_loader.load()

    # Add plan mode prompt if requested
    if plan_mode:  # pragma: no cover
        from henchman.cli.commands.plan import PLAN_MODE_PROMPT
        system_prompt += PLAN_MODE_PROMPT

    config = ReplConfig(system_prompt=system_prompt)
    repl = Repl(provider=provider, console=console, config=config)

    # Set plan mode if requested
    if plan_mode and repl.session:  # pragma: no cover
        repl.session.plan_mode = True
        repl.tool_registry.set_plan_mode(True)

    async def run_single_prompt_text() -> None:  # pragma: no cover
        """Process a single prompt and exit with text output."""
        async for event in repl.agent.run(prompt):
            if event.type == EventType.CONTENT:
                console.print(event.data, end="")
            elif event.type == EventType.FINISHED:
                console.print()

    async def run_single_prompt_json() -> None:
        """Process a single prompt and exit with JSON output."""
        json_renderer = JsonOutputRenderer(console)
        async for event in repl.agent.run(prompt):
            json_renderer.render(event)

    async def run_single_prompt_stream_json() -> None:
        """Process a single prompt and exit with streaming JSON output."""
        json_renderer = JsonOutputRenderer(console)
        async for event in repl.agent.run(prompt):
            json_renderer.render_stream_json(event)

    if output_format == "text":
        anyio.run(run_single_prompt_text)
    elif output_format == "json":
        anyio.run(run_single_prompt_json)
    elif output_format == "stream-json":
        anyio.run(run_single_prompt_stream_json)
    else:  # pragma: no cover
        pass


@click.command()
@click.version_option(version=VERSION, prog_name="mlg")
@click.option("-p", "--prompt", help="Run with a single prompt and exit")
@click.option(
    "--output-format",
    type=click.Choice(["text", "json", "stream-json"]),
    default="text",
    help="Output format for responses",
)
@click.option(
    "--plan",
    is_flag=True,
    default=False,
    help="Start in plan mode (read-only)",
)
def cli(prompt: str | None, output_format: str, plan: bool) -> None:
    """Henchman-AI: A model-agnostic AI agent CLI.

    Start an interactive session or run with --prompt for headless mode.
    """
    if prompt:
        _run_headless(prompt, output_format, plan)
    else:
        _run_interactive(output_format, plan)


def main() -> None:  # pragma: no cover
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
