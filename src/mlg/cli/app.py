"""MLG CLI application entry point."""

import click
from rich.console import Console

from mlg.version import VERSION

console = Console()


@click.command()
@click.version_option(version=VERSION, prog_name="mlg")
@click.option("-p", "--prompt", help="Run with a single prompt and exit")
@click.option(
    "--output-format",
    type=click.Choice(["text", "json", "stream-json"]),
    default="text",
    help="Output format for responses",
)
def cli(prompt: str | None, output_format: str) -> None:  # noqa: ARG001
    """MLG-CLI: A model-agnostic AI agent CLI.

    Start an interactive session or run with --prompt for headless mode.
    """
    if prompt:
        # Headless mode - run single prompt
        console.print(f"[dim]Prompt: {prompt}[/]")
        console.print("[yellow]Not yet implemented[/]")
        return

    # Interactive mode
    console.print("[bold blue]MLG-CLI[/] - /help for commands, /quit to exit\n")
    console.print("[yellow]Interactive mode not yet implemented[/]")


def main() -> None:  # pragma: no cover
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
