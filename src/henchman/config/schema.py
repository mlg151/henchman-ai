"""Configuration schema using Pydantic models.

This module defines the settings schema for henchman-cli configuration.
Settings are loaded from YAML/JSON files and environment variables.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AgentConfig(BaseModel):
    """Configuration for an agent in the team."""

    name: str = Field(..., description="Display name of the agent")
    role: str = Field(..., description="Unique role identifier")
    description: str = Field(..., description="One-line description of the agent's purpose")
    system_prompt: str | None = Field(
        None, description="Role-specific instructions (None for default)"
    )
    tools: list[str] = Field(default_factory=list, description="Allowlist of tool names")
    provider: str | None = Field(None, description="Override model provider")
    model: str | None = Field(None, description="Override model name")
    auto_approve: list[str] = Field(default_factory=list, description="Tools to auto-approve")
    can_delegate_to: list[str] = Field(
        default_factory=list, description="Roles this agent can delegate to"
    )
    enabled: bool = Field(True, description="Whether this agent is active")

    @field_validator("tools")
    @classmethod
    def tools_must_not_be_empty(cls, v: list[str]) -> list[str]:
        """Validate that agent has at least one tool.

        Args:
            v: List of tool names.

        Returns:
            The validated list.

        Raises:
            ValueError: If the list is empty.
        """
        if not v:
            raise ValueError("Agent must have at least one tool")
        return v


class ProviderSettings(BaseModel):
    """Settings for model providers.

    Attributes:
        default: The default provider to use.
        deepseek: DeepSeek provider configuration.
        openai: OpenAI provider configuration.
        anthropic: Anthropic provider configuration.
        ollama: Ollama provider configuration.
    """

    default: str = "deepseek"
    deepseek: dict[str, object] = Field(
        default_factory=lambda: dict[str, object]({"model": "deepseek-chat"})
    )
    openai: dict[str, object] = Field(default_factory=dict)
    anthropic: dict[str, object] = Field(default_factory=dict)
    ollama: dict[str, object] = Field(
        default_factory=lambda: dict[str, object]({"base_url": "http://localhost:11434"})
    )
    openrouter: dict[str, object] = Field(default_factory=dict)
    openai_compat: dict[str, object] = Field(default_factory=dict)
    together: dict[str, object] = Field(default_factory=dict)
    groq: dict[str, object] = Field(default_factory=dict)
    fireworks: dict[str, object] = Field(default_factory=dict)


class ToolSettings(BaseModel):
    """Settings for tool behavior.

    Attributes:
        auto_approve_read: Whether to auto-approve read-only tools.
        shell_timeout: Default timeout for shell commands in seconds.
        sandbox: Execution sandbox mode ("none" or "docker").
    """

    auto_approve_read: bool = True
    shell_timeout: int = 3600
    sandbox: Literal["none", "docker"] = "none"


class UISettings(BaseModel):
    """Settings for terminal UI.

    Attributes:
        theme: UI color theme name.
        show_line_numbers: Whether to show line numbers in file output.
        mcp_logging: Whether to show MCP connection/logging messages in terminal.
    """

    theme: str = "dark"
    show_line_numbers: bool = True
    mcp_logging: bool = False
    accessible_mode: bool = False
    keybindings: dict[str, str] = Field(
        default_factory=lambda: {
            "c-c": "abort",
            "c-d": "exit",
        }
    )
    style_overrides: dict[str, str] = Field(default_factory=dict)


class ContextSettings(BaseModel):
    """Settings for context management.

    Attributes:
        max_tokens: Maximum tokens to keep in context before compaction.
        compaction_threshold: Percentage of max_tokens at which to start compaction.
        auto_compact: Whether to automatically compact context.
    """

    max_tokens: int = 128000
    compaction_threshold: float = 0.75  # 75% of max_tokens
    auto_compact: bool = True


class McpServerConfig(BaseModel):
    """Configuration for an MCP server.

    Attributes:
        command: The command to run the MCP server.
        args: Command line arguments.
        env: Environment variables to set.
        trusted: Whether to skip confirmation for this server's tools.
    """

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    trusted: bool = False


class AgentSettings(BaseModel):
    """Settings for the multi-agent system.

    Attributes:
        team_preset: Which preset team to use ("default").
        agents: Custom agent configurations or overrides.
        max_delegation_depth: Maximum recursive delegation depth.
        max_delegation_turns: Maximum tool-call turns per specialist delegation.
        shared_context_max_tokens: Max tokens for shared context between agents.
    """

    team_preset: str = "default"
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    max_delegation_depth: int = 3
    max_delegation_turns: int = 150
    shared_context_max_tokens: int = 4000


class RagSettings(BaseModel):
    """Settings for RAG (Retrieval Augmented Generation).

    Attributes:
        enabled: Whether RAG is enabled.
        chunk_size: Target tokens per chunk.
        chunk_overlap: Token overlap between chunks.
        top_k: Number of results to return from search.
        embedding_model: FastEmbed model name.
        cache_dir: Optional custom directory for RAG cache.
            If not set, uses ~/.henchman/rag_indices/
        file_extensions: File extensions to index.
    """

    enabled: bool = True
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    cache_dir: str | None = None
    file_extensions: list[str] = Field(
        default_factory=lambda: [
            # Python
            ".py",
            ".pyx",
            ".pyi",
            ".pyw",
            # JavaScript/TypeScript
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".mjs",
            ".cjs",
            # Web
            ".html",
            ".htm",
            ".css",
            ".scss",
            ".sass",
            ".less",
            # Data formats
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".xml",
            # Documentation
            ".md",
            ".markdown",
            ".rst",
            ".txt",
            # Shell
            ".sh",
            ".bash",
            ".zsh",
            ".fish",
            # C/C++
            ".c",
            ".h",
            ".cpp",
            ".hpp",
            ".cc",
            ".hh",
            ".cxx",
            # Java/Kotlin
            ".java",
            ".kt",
            ".kts",
            # Go
            ".go",
            # Rust
            ".rs",
            # Ruby
            ".rb",
            ".rake",
            # PHP
            ".php",
            # Swift
            ".swift",
            # Config
            ".ini",
            ".cfg",
            ".conf",
            # Other
            ".sql",
            ".graphql",
            ".proto",
        ]
    )


class Settings(BaseModel):
    """Main settings model for henchman-cli.

    Attributes:
        providers: Provider configuration.
        tools: Tool behavior configuration.
        ui: UI settings.
        context: Context management settings.
        mcp_servers: MCP server configurations.
        rag: RAG (Retrieval Augmented Generation) settings.
    """

    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    ui: UISettings = Field(default_factory=UISettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    mcp_servers: dict[str, McpServerConfig] = Field(default_factory=dict)
    rag: RagSettings = Field(default_factory=RagSettings)
    agents: AgentSettings = Field(default_factory=AgentSettings)
