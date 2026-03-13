"""Shared console helper functions for CLI commands."""

from typing import Any


def _print_line(console: Any, text: str) -> None:
    """Print a single formatted line to the console.

    Args:
        console: Console for output.
        text: Formatted text to print.
    """
    console.print(text)


def print_usage_help(
    console: Any,
    usage: str,
    commands: list[tuple[str, str]],
    header: str = "Commands:",
) -> None:
    """Print usage help with command list.

    Args:
        console: Console for output.
        usage: Usage string.
        commands: List of (command, description) tuples.
        header: Header text for the commands section (default: "Commands:").

    Returns:
        None
    """
    console.print(f"[yellow]Usage: {usage}[/]")
    if commands:
        console.print(f"\n{header}")
        for command, description in commands:
            console.print(f"  {command} - {description}")
    console.print("")


def print_parameter_list(
    console: Any,
    parameters: list[tuple[str, str]],
    header: str = "Parameters:",
) -> None:
    """Print a list of parameters with descriptions.

    Args:
        console: Console for output.
        parameters: List of (parameter, description) tuples.
        header: Header text for the parameters section (default: "Parameters:").

    Returns:
        None
    """
    console.print(f"\n{header}")
    for param, description in parameters:
        console.print(f"  {param:<25} - {description}")


class ConsoleHelper:
    """Helper class for console output operations."""

    @staticmethod
    def print_status_header(console: Any, title: str) -> None:
        """Print status header.

        Args:
            console: Console for output.
            title: Title for the header.

        Returns:
            None
        """
        _print_line(console, f"\n[bold blue]{title}[/]\n")

    @staticmethod
    def print_status_value(console: Any, label: str, value: Any, color: str = "cyan") -> None:
        """Print a status value with consistent formatting.

        Args:
            console: Console for output.
            label: Label for the value.
            value: Value to display.
            color: Color for the value.

        Returns:
            None
        """
        console.print(f"  {label}: [{color}]{value}[/]")

    @staticmethod
    def print_enabled_status(console: Any, label: str, *, is_enabled: bool) -> None:
        """Print enabled/disabled status with appropriate colors.

        Args:
            console: Console for output.
            label: Label for the status.
            is_enabled: Whether the feature is enabled.

        Returns:
            None
        """
        color = "green" if is_enabled else "yellow"
        status = "Enabled" if is_enabled else "Disabled"
        console.print(f"  {label}: [{color}]{status}[/]")

    @staticmethod
    def print_command_help(console: Any, command: str, description: str) -> None:
        """Print command help line.

        Args:
            console: Console for output.
            command: Command syntax.
            description: Command description.

        Returns:
            None
        """
        console.print(f"  Use [cyan]{command}[/] to {description}")

    @staticmethod
    def print_error_message(console: Any, error: str, usage: str | None = None) -> None:
        """Print error message with optional usage help.

        Args:
            console: Console for output.
            error: Error message to display.
            usage: Optional usage string to show.

        Returns:
            None
        """
        console.print(f"[red]Error:[/] {error}")
        if usage:
            console.print(f"[yellow]Usage:[/] {usage}")

    @staticmethod
    def print_usage_help(
        console: Any,
        usage: str,
        commands: list[tuple[str, str]],
        header: str = "Commands:",
    ) -> None:
        """Print usage help with command list.

        Args:
            console: Console for output.
            usage: Usage string.
            commands: List of (command, description) tuples.
            header: Header text for the commands section (default: "Commands:").

        Returns:
            None
        """
        print_usage_help(console, usage, commands, header)

    @staticmethod
    def print_parameter_list(
        console: Any,
        parameters: list[tuple[str, str]],
        header: str = "Parameters:",
    ) -> None:
        """Print a list of parameters with descriptions.

        Args:
            console: Console for output.
            parameters: List of (parameter, description) tuples.
            header: Header text for the parameters section (default: "Parameters:").

        Returns:
            None
        """
        print_parameter_list(console, parameters, header)
