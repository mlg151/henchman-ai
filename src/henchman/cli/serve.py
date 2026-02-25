"""Serve command for Henchman-AI API server."""

from __future__ import annotations

import click
from rich.console import Console

from henchman.api.server import run_server
from henchman.config import load_settings


@click.command(name="serve")
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind the server to",
    show_default=True,
)
@click.option(
    "--port",
    default=8000,
    type=int,
    help="Port to bind the server to",
    show_default=True,
)
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Enable auto-reload for development",
)
@click.option(
    "--workers",
    default=1,
    type=int,
    help="Number of worker processes",
    show_default=True,
)
def serve_command(
    host: str,
    port: int,
    reload: bool,
    workers: int,
) -> None:
    """Start the Henchman-AI API server.

    This command starts a FastAPI server that provides REST API access
    to Henchman-AI functionality.

    Examples:
        henchman serve
        henchman serve --host 0.0.0.0 --port 8080
        henchman serve --reload  # Development mode
    """
    console = Console()

    # Load settings to check API configuration
    settings = load_settings()

    # Show server info
    console.print("[bold green]Starting Henchman-AI API server...[/]")
    console.print(f"  Host: [cyan]{host}[/]")
    console.print(f"  Port: [cyan]{port}[/]")
    console.print(f"  Reload: [cyan]{'enabled' if reload else 'disabled'}[/]")
    console.print(f"  Workers: [cyan]{workers}[/]")

    if settings.api and hasattr(settings.api, "require_auth"):
        if settings.api.require_auth:
            console.print("  Authentication: [yellow]required[/]")
            if hasattr(settings.api, "api_keys") and settings.api.api_keys:
                console.print(f"  API keys configured: [cyan]{len(settings.api.api_keys)}[/]")
            else:
                console.print("  [yellow]Warning: No API keys configured[/]")
        else:
            console.print("  Authentication: [green]disabled[/]")

    console.print(f"\n[dim]API documentation will be available at: http://{host}:{port}/docs[/]")
    console.print("[dim]Press Ctrl+C to stop the server[/]\n")

    # Run the server
    try:
        run_server(
            host=host,
            port=port,
            reload=reload,
            workers=workers,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/]")
    except Exception as e:
        console.print(f"\n[red]Error starting server: {e}[/]")
        raise click.ClickException(f"Failed to start server: {e}")
