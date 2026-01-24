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
    except Exception:
        pass

    raise click.ClickException(
        "No API key configured. Set DEEPSEEK_API_KEY or configure in ~/.henchman/settings.yaml"
    )


def _run_interactive(output_format: str) -> None:  # noqa: ARG001
    """Run interactive REPL mode.

    Args:
        output_format: Output format (text, json, stream-json).
    """
    from henchman.cli.repl import Repl, ReplConfig
    from henchman.config import ContextLoader

    provider = _get_provider()

    # Load context from MLG.md files
    context_loader = ContextLoader()
    system_prompt = context_loader.load()

    config = ReplConfig(system_prompt=system_prompt)
    repl = Repl(provider=provider, console=console, config=config)

    anyio.run(repl.run)


def _run_headless(prompt: str, output_format: str) -> None:  # noqa: ARG001
    """Run headless mode with a single prompt.

    Args:
        prompt: The prompt to process.
        output_format: Output format (text, json, stream-json).
    """
    from henchman.cli.repl import Repl, ReplConfig
    from henchman.config import ContextLoader
    from henchman.core.events import EventType

    provider = _get_provider()

    # Load context from MLG.md files
    context_loader = ContextLoader()
    system_prompt = context_loader.load()

    config = ReplConfig(system_prompt=system_prompt)
    repl = Repl(provider=provider, console=console, config=config)

    async def run_single_prompt() -> None:  # pragma: no cover
        """Process a single prompt and exit."""
        async for event in repl.agent.run(prompt):
            if event.type == EventType.CONTENT:
                console.print(event.data, end="")
            elif event.type == EventType.FINISHED:
                console.print()

    anyio.run(run_single_prompt)


@click.command()
@click.version_option(version=VERSION, prog_name="mlg")
@click.option("-p", "--prompt", help="Run with a single prompt and exit")
@click.option(
    "--output-format",
    type=click.Choice(["text", "json", "stream-json"]),
    default="text",
    help="Output format for responses",
)
def cli(prompt: str | None, output_format: str) -> None:
    """Henchman-AI: A model-agnostic AI agent CLI.

    Start an interactive session or run with --prompt for headless mode.
    """
    if prompt:
        _run_headless(prompt, output_format)
    else:
        _run_interactive(output_format)


def main() -> None:  # pragma: no cover
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
