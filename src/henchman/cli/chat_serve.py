"""Chat serve command for starting chat bot integrations."""

from __future__ import annotations

import asyncio
from typing import Any

import click
from rich.console import Console

from henchman.config import load_settings


@click.command(name="xyzbot")
@click.option(
    "--platform",
    type=click.Choice(["discord"], case_sensitive=False),
    default="discord",
    help="Chat platform to use",
    show_default=True,
)
@click.option(
    "--token",
    envvar="DISCORD_TOKEN",
    help="Bot token (or set DISCORD_TOKEN env var)",
)
@click.option(
    "--user-id",
    envvar="DISCORD_USER_ID",
    help="Authorized user ID (or set DISCORD_USER_ID env var)",
)
def xyzbot_command(
    platform: str,
    token: str | None,
    user_id: str | None,
) -> None:
    """Start a chat bot for remote Henchman-AI access.

    This command starts a chat bot (e.g., Discord) that allows you to
    interact with Henchman-AI remotely from your phone or browser.

    Args:
        platform: Chat platform to use (currently only "discord" supported).
        token: Bot token for the chat platform. Can be provided via CLI,
            environment variable (DISCORD_TOKEN), or settings file.
        user_id: Authorized user ID for the chat platform. Can be provided
            via CLI, environment variable (DISCORD_USER_ID), or settings file.

    Returns:
        None. This is a Click command that starts a bot and runs until
        interrupted.

    Examples:
        henchman chatbot
        henchman chatbot --platform discord
        DISCORD_TOKEN=xxx DISCORD_USER_ID=yyy henchman chatbot
    """
    import sys
    print(f"DEBUG: discordbot_command called with platform={platform}, token={token}, user_id={user_id}", file=sys.stderr)
    console = Console()

    # Load settings
    settings = load_settings()

    # Get token and user ID from settings if not provided via CLI/env
    if token is None and hasattr(settings, "chat") and settings.chat.discord.token:
        token = settings.chat.discord.token
    if user_id is None and hasattr(settings, "chat") and settings.chat.discord.allowed_user_id:
        user_id = settings.chat.discord.allowed_user_id

    # Validate required parameters
    if not token:
        console.print(
            "[red]Error:[/] Discord bot token is required.\n\n"
            "Set it via:\n"
            "  • Environment variable: [cyan]DISCORD_TOKEN[/]\n"
            "  • CLI flag: [cyan]--token <TOKEN>[/]\n"
            "  • Settings file: [cyan]chat.discord.token[/]"
        )
        raise click.Abort

    if not user_id:
        console.print(
            "[red]Error:[/] Discord user ID is required.\n\n"
            "Set it via:\n"
            "  • Environment variable: [cyan]DISCORD_USER_ID[/]\n"
            "  • CLI flag: [cyan]--user-id <ID>[/]\n"
            "  • Settings file: [cyan]chat.discord.allowed_user_id[/]\n\n"
            "[dim]To find your Discord user ID:\n"
            "  1. Enable Developer Mode in Discord settings\n"
            "  2. Right-click your username → Copy User ID[/]"
        )
        raise click.Abort

    # Show startup info
    console.print("[bold green]Starting Henchman-AI chat bot...[/]")
    console.print(f"  Platform: [cyan]{platform}[/]")
    console.print(f"  Provider: [cyan]{settings.providers.default}[/]")
    console.print(f"  User ID: [cyan]{user_id}[/]")
    console.print("\n[dim]Press Ctrl+C to stop the bot[/]\n")

    # Run the bot
    try:
        asyncio.run(_run_discord_bot(token, user_id, settings))
    except KeyboardInterrupt:
        console.print("\n[yellow]Bot stopped by user[/]")
    except ImportError as e:
        console.print(f"\n[red]{e}[/]")
        raise click.Abort from e
    except Exception as e:
        console.print(f"\n[red]Error starting bot: {e}[/]")
        raise click.Abort from e


async def _run_discord_bot(
    token: str,
    user_id: str,
    settings: Any,
) -> None:
    """Run the Discord bot.

    Args:
        token: Discord bot token.
        user_id: Authorized user ID.
        settings: Henchman-AI settings.

    Returns:
        None
    """
    from henchman.chat.manager import ChatManager

    manager = ChatManager(settings)
    manager.create_discord_bot(token=token, allowed_user_id=user_id)

    try:
        await manager.start_all()
    finally:
        await manager.stop_all()
