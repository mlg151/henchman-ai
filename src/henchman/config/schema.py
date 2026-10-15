"""Configuration schema using Pydantic models.

This module defines the settings schema for henchman-cli configuration.
Settings are loaded from YAML/JSON files and environment variables.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

DEFAULT_SHELL_TIMEOUT = 3600
"""Default shell command timeout in seconds."""

DEFAULT_MAX_TOKENS = 8000
"""Default maximum tokens to keep in context."""

DEFAULT_COMPACTION_THRESHOLD = 0.75
"""Default compaction threshold as a fraction of max_tokens."""

DEFAULT_CLUSTER_SIMILARITY_THRESHOLD = 0.7
"""Default similarity threshold for clustering messages."""

DEFAULT_MAX_DELEGATION_DEPTH = 3
"""Default maximum recursive delegation depth."""

DEFAULT_MAX_DELEGATION_TURNS = 150
"""Default maximum tool-call turns per specialist delegation."""

DEFAULT_SHARED_CONTEXT_TOKENS = 2000
"""Default max tokens for shared context between agents."""

DEFAULT_MAX_DELEGATION_RETRIES = 1
"""Default number of automatic retries for a failed specialist delegation."""

DEFAULT_RAG_CHUNK_SIZE = 512
"""Default target tokens per RAG chunk."""

DEFAULT_RAG_CHUNK_OVERLAP = 50
"""Default token overlap between RAG chunks."""

DEFAULT_RAG_TOP_K = 5
"""Default number of results to return from RAG search."""


class AgentConfig(BaseModel):
    """Configuration for an agent in the team."""

    name: str = Field(..., description="Display name of the agent")
    role: str = Field(..., description="Unique role identifier")
    description: str = Field(..., description="One-line description of the agent's purpose")
    system_prompt: str | None = Field(
        None,
        description="Role-specific instructions (None for default)",
    )
    tools: list[str] = Field(default_factory=list, description="Allowlist of tool names")
    provider: str | None = Field(None, description="Override model provider")
    model: str | None = Field(None, description="Override model name")
    auto_approve: list[str] = Field(default_factory=list, description="Tools to auto-approve")
    can_delegate_to: list[str] = Field(
        default_factory=list,
        description="Roles this agent can delegate to",
    )
    enabled: bool = Field(default=True, description="Whether this agent is active")

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
            msg = "Agent must have at least one tool"
            raise ValueError(msg)
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
        default_factory=lambda: dict[str, object]({"model": "deepseek-chat"}),
    )
    openai: dict[str, object] = Field(default_factory=dict)
    anthropic: dict[str, object] = Field(default_factory=dict)
    ollama: dict[str, object] = Field(default_factory=dict)
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
    shell_timeout: int = Field(DEFAULT_SHELL_TIMEOUT, ge=1)
    sandbox: Literal["none", "docker"] = "none"


UI_OUTPUT_STYLES: list[str] = ["verbose", "concise", "minimal", "json"]
"""Valid output style names for the UI."""

UI_THEME_NAMES: list[str] = [
    "dark",
    "light",
    "monokai",
    "dracula",
    "nord",
    "solarized-dark",
    "solarized-light",
    "one-dark",
    "github-dark",
    "github-light",
]
"""Valid theme names for the UI."""


class UISettings(BaseModel):
    """Settings for terminal UI.

    Attributes:
        theme: UI color theme name.
        show_line_numbers: Whether to show line numbers in file output.
        mcp_logging: Whether to show MCP connection/logging messages in terminal.
        output_style: Output verbosity style (verbose, concise, minimal).
        accessible_mode: Whether to enable accessibility mode.
        keybindings: Custom keybinding mappings.
        style_overrides: Custom style overrides.
    """

    theme: str = "dark"
    show_line_numbers: bool = True
    mcp_logging: bool = False
    output_style: str = "verbose"
    accessible_mode: bool = False
    keybindings: dict[str, str] = Field(
        default_factory=lambda: {
            "c-c": "abort",
            "c-d": "exit",
        },
    )
    style_overrides: dict[str, str] = Field(default_factory=dict)

    @field_validator("theme")
    @classmethod
    def theme_must_be_known(cls, v: str) -> str:
        """Reject unknown theme names.

        Args:
            v: The theme name.

        Returns:
            The validated theme name.

        Raises:
            ValueError: If the theme is not in the known list.
        """
        if v not in UI_THEME_NAMES:
            raise ValueError(f"Unsupported theme '{v}'")
        return v

    @field_validator("keybindings")
    @classmethod
    def keybindings_must_not_be_blank(cls, v: dict[str, str]) -> dict[str, str]:
        """Reject keybinding actions that are blank.

        Args:
            v: The keybindings mapping.

        Returns:
            The validated keybindings.

        Raises:
            ValueError: If any keybinding action is empty or only whitespace.
        """
        for action in v.values():
            if not action.strip():
                raise ValueError("Keybinding actions must not be blank")
        return v


class ContextSettings(BaseModel):
    """Settings for context management.

    Attributes:
        max_tokens: Maximum tokens to keep in context before compaction.
        compaction_threshold: Percentage of max_tokens at which to start compaction.
        auto_compact: Whether to automatically compact context.
        intelligent_context: Whether to use intelligent context management.
        importance_threshold: Minimum importance score to preserve a message.
        cluster_similarity_threshold: Similarity threshold for clustering messages.
        adaptive_compression: Whether to use adaptive compression techniques.
    """

    max_tokens: int = Field(DEFAULT_MAX_TOKENS, ge=1)
    compaction_threshold: float = Field(DEFAULT_COMPACTION_THRESHOLD, ge=0, le=1)  # 75% of max_tokens
    auto_compact: bool = True
    intelligent_context: bool = False
    importance_threshold: float = Field(0.5, ge=0, le=1)
    cluster_similarity_threshold: float = Field(DEFAULT_CLUSTER_SIMILARITY_THRESHOLD, ge=0, le=1)
    adaptive_compression: bool = True


class McpServerConfig(BaseModel):
    """Configuration for an MCP server.

    Attributes:
        command: The command to run the MCP server.
        args: Command line arguments.
        env: Environment variables to set.
        trusted: Whether to skip confirmation for this server's tools.
    """

    command: str = Field(..., min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    trusted: bool = False

    @field_validator("command")
    @classmethod
    def command_must_not_be_whitespace(cls, v: str) -> str:
        """Reject commands that are only whitespace.

        Args:
            v: The command string.

        Returns:
            The validated command string.

        Raises:
            ValueError: If the command is empty or only whitespace.
        """
        if not v.strip():
            raise ValueError("MCP server command must not be empty or whitespace")
        return v


class AgentSettings(BaseModel):
    """Settings for the multi-agent system.

    Attributes:
        team_preset: Which preset team to use ("default").
        agents: Custom agent configurations or overrides.
        max_delegation_depth: Maximum recursive delegation depth.
        max_delegation_turns: Maximum tool-call turns per specialist delegation.
        shared_context_max_tokens: Max tokens for shared context between agents.
        max_delegation_retries: How many times to automatically retry a failed
            specialist delegation before surfacing the failure to the Tech Lead.
    """

    team_preset: str = "default"
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    max_delegation_depth: int = Field(DEFAULT_MAX_DELEGATION_DEPTH, ge=1)
    max_delegation_turns: int = Field(DEFAULT_MAX_DELEGATION_TURNS, ge=1)
    shared_context_max_tokens: int = Field(DEFAULT_SHARED_CONTEXT_TOKENS, ge=1)
    max_delegation_retries: int = Field(DEFAULT_MAX_DELEGATION_RETRIES, ge=0)

    @field_validator("agents", mode="before")
    @classmethod
    def merge_builtin_role_overrides(cls, value: Any) -> Any:
        """Fill builtin role mappings from presets, retaining explicit field values."""
        if not isinstance(value, Mapping) or not value:
            return value
        from henchman.agents.presets import get_default_team

        presets = get_default_team()
        return {
            role: {**presets[role].model_dump(), **config}
            if role in presets and isinstance(config, Mapping)
            else config
            for role, config in value.items()
        }


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
    chunk_size: int = Field(DEFAULT_RAG_CHUNK_SIZE, ge=1)
    chunk_overlap: int = Field(DEFAULT_RAG_CHUNK_OVERLAP, ge=0)
    top_k: int = Field(DEFAULT_RAG_TOP_K, ge=1)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    cache_dir: str | None = None

    @model_validator(mode="after")
    def chunk_overlap_must_be_less_than_chunk_size(self) -> RagSettings:
        """Ensure chunk_overlap is less than chunk_size.

        Returns:
            The validated RagSettings instance.

        Raises:
            ValueError: If chunk_overlap >= chunk_size.
        """
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than "
                f"chunk_size ({self.chunk_size})"
            )
        return self

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
        ],
    )


class ApiConfig(BaseModel):
    """API server configuration.

    Attributes:
        require_auth: Whether API authentication is required.
        api_keys: List of valid API keys.
        rate_limits: Rate limit configuration.
        proxy: Upstream proxy configuration (base_url, headers, etc.).
        cors: CORS configuration.
    """

    require_auth: bool = Field(default=False, description="Whether API authentication is required")
    api_keys: list[str] = Field(default_factory=list, description="List of valid API keys")
    rate_limits: dict[str, str] = Field(
        default_factory=lambda: {"default": "100/hour"},
        description="Rate limit configuration (e.g., '100/hour', '1000/day')",
    )
    proxy: dict[str, Any] = Field(
        default_factory=dict,
        description="Upstream proxy configuration (base_url, headers, etc.)",
    )
    cors: dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "origins": ["*"]},
        description="CORS configuration",
    )


class DiscordSettings(BaseModel):
    """Discord bot configuration.

    Attributes:
        enabled: Whether the Discord bot is enabled.
        token: Discord bot token (or env var reference).
        allowed_user_id: Discord user ID authorized to use the bot.
        system_prompt: Custom system prompt for Discord conversations.
    """

    model_config = {"extra": "forbid"}

    enabled: bool = Field(default=False, description="Whether the Discord bot is enabled")
    token: str | None = Field(
        default=None,
        description="Discord bot token (set via DISCORD_TOKEN env var or here)",
    )
    allowed_user_id: str | None = Field(
        default=None,
        description="Discord user ID (snowflake) authorized to use the bot",
    )
    allowed_channel_ids: list[str] = Field(
        default_factory=list,
        description="List of Discord channel IDs the bot is allowed to respond in",
    )
    mention_only: bool = Field(
        default=False,
        description="Whether the bot only responds when mentioned",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Custom system prompt for Discord conversations",
    )


class SlackSettings(BaseModel):
    """Slack bot configuration.

    Attributes:
        enabled: Whether the Slack bot is enabled.
        app_token: Slack app-level token.
        bot_token: Slack bot token.
        signing_secret: Slack signing secret.
        allowed_user_id: Slack user ID authorized to use the bot.
    """

    model_config = {"extra": "forbid"}

    enabled: bool = Field(default=False, description="Whether the Slack bot is enabled")
    app_token: str | None = Field(default=None, description="Slack app-level token")
    bot_token: str | None = Field(default=None, description="Slack bot token")
    signing_secret: str | None = Field(default=None, description="Slack signing secret")
    allowed_user_id: str | None = Field(
        default=None, description="Slack user ID authorized to use the bot"
    )


class VoiceSettings(BaseModel):
    """Voice integration configuration.

    Attributes:
        enabled: Whether voice features are enabled.
        preferred_voice: Preferred voice name/ID for TTS.
        tts_command: Shell command template for text-to-speech.
        stt_command: Shell command template for speech-to-text.
    """

    model_config = {"extra": "forbid"}

    enabled: bool = Field(default=False, description="Whether voice features are enabled")
    preferred_voice: str | None = Field(default=None, description="Preferred voice name/ID")
    tts_command: list[str] = Field(default_factory=list, description="TTS command template")
    stt_command: list[str] = Field(default_factory=list, description="STT command template")


class ChatConfig(BaseModel):
    """Chat integration configuration.

    Attributes:
        discord: Discord bot settings.
        slack: Slack bot settings.
    """

    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)


class Settings(BaseModel):
    """Main settings model for henchman-cli.

    Attributes:
        providers: Provider configuration.
        tools: Tool behavior configuration.
        ui: UI settings.
        context: Context management settings.
        mcp_servers: MCP server configurations.
        rag: RAG (Retrieval Augmented Generation) settings.
        api: API server configuration.
        chat: Chat integration configuration.
    """

    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    ui: UISettings = Field(default_factory=UISettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    mcp_servers: dict[str, McpServerConfig] = Field(default_factory=dict)
    rag: RagSettings = Field(default_factory=RagSettings)
    agents: AgentSettings = Field(default_factory=AgentSettings)
    api: ApiConfig = Field(default_factory=ApiConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
