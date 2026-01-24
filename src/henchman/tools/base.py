"""Tool base classes and types for Henchman-AI."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from henchman.providers.base import ToolDeclaration


class ToolKind(Enum):
    """Classification of tool types for confirmation policies.

    Tools are classified by their potential impact:
    - READ: Safe, read-only operations (auto-approved)
    - WRITE: Modifies files or state (requires confirmation)
    - EXECUTE: Runs arbitrary code/commands (requires confirmation)
    - NETWORK: Makes network requests (requires confirmation)
    """

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        content: The result content to send back to the model.
        success: Whether the tool executed successfully.
        display: Optional different display for the user (vs content for model).
        error: Optional error message if success is False.
    """

    content: str
    success: bool = True
    display: str | None = None
    error: str | None = None


@dataclass
class ConfirmationRequest:
    """Request for user confirmation before executing a tool.

    Attributes:
        tool_name: Name of the tool requesting confirmation.
        description: Human-readable description of the action.
        params: Optional parameters being passed to the tool.
        risk_level: Risk level indicator ("low", "medium", "high").
    """

    tool_name: str
    description: str
    params: dict[str, object] | None = None
    risk_level: str = field(default="medium")


class Tool(ABC):
    """Abstract base class for all tools.

    Tools are operations that the LLM can request to perform. Each tool
    must define its name, description, parameter schema, and execution logic.

    Example:
        >>> class ReadFileTool(Tool):
        ...     @property
        ...     def name(self) -> str:
        ...         return "read_file"
        ...     @property
        ...     def description(self) -> str:
        ...         return "Read contents of a file"
        ...     @property
        ...     def parameters(self) -> dict:
        ...         return {"type": "object", "properties": {"path": {"type": "string"}}}
        ...     @property
        ...     def kind(self) -> ToolKind:
        ...         return ToolKind.READ
        ...     async def execute(self, **params) -> ToolResult:
        ...         return ToolResult(content="file contents")
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""
        ...  # pragma: no cover

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        ...  # pragma: no cover

    @property
    @abstractmethod
    def parameters(self) -> dict[str, object]:
        """JSON Schema describing the tool's parameters."""
        ...  # pragma: no cover

    @property
    def kind(self) -> ToolKind:
        """The kind of tool, used for confirmation policies.

        Override this in subclasses to specify the tool's risk level.
        Defaults to READ (auto-approved).
        """
        return ToolKind.READ

    def needs_confirmation(
        self, params: dict[str, object]
    ) -> ConfirmationRequest | None:
        """Check if this tool needs user confirmation.

        Args:
            params: The parameters being passed to the tool.

        Returns:
            A ConfirmationRequest if confirmation is needed, None otherwise.
            By default, READ tools don't need confirmation, while
            WRITE, EXECUTE, and NETWORK tools do.
        """
        if self.kind in (ToolKind.WRITE, ToolKind.EXECUTE, ToolKind.NETWORK):
            return ConfirmationRequest(
                tool_name=self.name,
                description=f"Execute {self.name} with parameters",
                params=params,
                risk_level="high" if self.kind == ToolKind.EXECUTE else "medium",
            )
        return None

    def to_declaration(self) -> ToolDeclaration:
        """Convert this tool to a ToolDeclaration for the LLM.

        Returns:
            A ToolDeclaration with the tool's name, description, and parameters.
        """
        return ToolDeclaration(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    @abstractmethod
    async def execute(self, **params: object) -> ToolResult:
        """Execute the tool with the given parameters.

        Args:
            **params: Tool-specific parameters.

        Returns:
            A ToolResult containing the execution result.
        """
        ...  # pragma: no cover
