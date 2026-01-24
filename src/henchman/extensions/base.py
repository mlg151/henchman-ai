"""Extension base class and types for Henchman-AI."""

from abc import ABC, abstractmethod

from henchman.cli.commands import Command
from henchman.tools.base import Tool


class Extension(ABC):
    """Abstract base class for extensions.

    Extensions allow third parties to add tools, commands, and context
    to the Henchman-AI. To create an extension, subclass this class and
    implement the required properties.

    Example:
        >>> class MyExtension(Extension):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_extension"
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...     @property
        ...     def description(self) -> str:
        ...         return "My custom extension"
        ...     def get_tools(self) -> list[Tool]:
        ...         return [MyCustomTool()]
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the extension.

        Returns:
            Extension name string.
        """
        ...  # pragma: no cover

    @property
    @abstractmethod
    def version(self) -> str:
        """Version string for the extension.

        Returns:
            Version string (e.g., "1.0.0").
        """
        ...  # pragma: no cover

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the extension.

        Returns:
            Description string.
        """
        ...  # pragma: no cover

    def get_tools(self) -> list[Tool]:
        """Return tools provided by this extension.

        Override this method to provide custom tools.

        Returns:
            List of Tool instances.
        """
        return []

    def get_commands(self) -> list[Command]:
        """Return slash commands provided by this extension.

        Override this method to provide custom commands.

        Returns:
            List of Command instances.
        """
        return []

    def get_context(self) -> str:
        """Return additional system prompt context.

        Override this method to add context to the system prompt.

        Returns:
            Context string to add to system prompt.
        """
        return ""
