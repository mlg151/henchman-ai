#!/usr/bin/env python3
"""Test script to debug Click command registration."""

import click

@click.group(invoke_without_command=True)
def cli():
    """Test CLI."""
    click.echo("CLI group invoked")

@cli.command(name="chat")
def chat_command():
    """Chat command."""
    click.echo("Chat command invoked")

@click.command(name="xyzbot")
def xyzbot_command():
    """XYZBot command."""
    click.echo("XYZBot command invoked")

# Add xyzbot command to CLI group
cli.add_command(xyzbot_command)

if __name__ == "__main__":
    cli()