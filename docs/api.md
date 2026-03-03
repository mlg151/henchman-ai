# API Reference

This page provides API reference for the main Henchman-AI modules.

## Core

### Agent

```python
from henchman.core import Agent, AgentEvent, EventType, AgentConfig, StallDetector, StreamContext, StreamState, EventBus, TurnState, TurnSummary, TurnSummaryRecord
```

#### Agent

The main agent class that orchestrates LLM interactions.

```python
class Agent:
    def __init__(
        self,
        provider: ModelProvider,
        tools: list[ToolDeclaration] | None = None,
        system_prompt: str = "",
        config: AgentConfig | None = None
    ) -> None:
        """Initialize the agent."""
    
    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the agent with user input, yielding events."""
    
    async def continue_with_tool_results(self) -> AsyncIterator[AgentEvent]:
        """Continue execution after tool results have been submitted."""
    
    def submit_tool_result(self, tool_call_id: str, result: str) -> None:
        """Submit a tool result for a pending tool call."""
    
    def clear_history(self) -> None:
        """Clear conversation history."""
    
    def get_messages_for_api(self) -> list[Message]:
        """Get messages for the API, with compaction if needed."""
```

#### AgentConfig

```python
@dataclass
class AgentConfig:
    system_prompt: str = ""
    model: str | None = None
    base_tool_iterations: int = 5
    intelligent_context: bool = True
    importance_threshold: float = 0.7
    cluster_similarity_threshold: float = 0.85
    adaptive_compression: bool = True
    max_protected_ratio: float = 0.3
    summarize_dropped: bool = True
```

#### EventType

```python
class EventType(Enum):
    CONTENT = "content"        # Text content from LLM
    THOUGHT = "thought"        # Thinking/reasoning
    TOOL_CALL_REQUEST = "tool_call_request"
    TOOL_CALL_RESULT = "tool_call_result"
    TOOL_CONFIRMATION = "tool_confirmation"  # User confirmation for tool execution
    ERROR = "error"
    FINISHED = "finished"
```

#### AgentEvent

```python
@dataclass
class AgentEvent:
    type: EventType
    data: Any
    source_agent: str | None = None  # Agent ID for multi-agent systems
```

#### EventBus

```python
class EventBus:
    def subscribe(self, event_type: EventType, callback: Callable[[AgentEvent], Any]) -> None:
        """Subscribe to events of a specific type."""
    
    def publish(self, event: AgentEvent) -> None:
        """Publish an event to all subscribers."""
    
    def unsubscribe(self, event_type: EventType, callback: Callable[[AgentEvent], Any]) -> None:
        """Unsubscribe from events."""
```

### Session

```python
from henchman.core import Session, SessionManager, SessionMessage, SessionMetadata
```

#### SessionManager

```python
class SessionManager:
    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize with session storage directory."""
    
    def create_session(
        self,
        project_hash: str,
        tag: str | None = None
    ) -> Session:
        """Create a new session."""
    
    def save(self, session: Session) -> None:
        """Save session to disk."""
    
    def load(self, session_id: str) -> Session | None:
        """Load session by ID."""
    
    def load_by_tag(
        self,
        tag: str,
        project_hash: str
    ) -> Session | None:
        """Load session by tag and project."""
    
    def list_sessions(
        self,
        project_hash: str | None = None
    ) -> list[SessionMetadata]:
        """List sessions, optionally filtered by project."""
    
    def delete(self, session_id: str) -> bool:
        """Delete a session."""
    
    def branch_session(
        self,
        session_id: str,
        branch_point: int,
        tag: str | None = None
    ) -> Session:
        """Create a branch from an existing session."""
    
    def merge_sessions(
        self,
        session_ids: list[str],
        strategy: str = "union",
        tag: str | None = None
    ) -> Session:
        """Merge multiple sessions."""
    
    def export_session(
        self,
        session_id: str,
        format: str = "json",
        include_metadata: bool = True
    ) -> str:
        """Export a session to string."""
    
    def import_session(
        self,
        data: str,
        format: str = "json",
        tag: str | None = None
    ) -> Session:
        """Import a session from string."""
    
    def save_template(
        self,
        session_id: str,
        name: str,
        description: str = "",
        parameters: dict[str, Any] | None = None
    ) -> str:
        """Save a session as a reusable template."""
    
    def create_from_template(
        self,
        template_id: str,
        parameters: dict[str, Any] | None = None,
        tag: str | None = None
    ) -> Session:
        """Create a new session from a template."""
    
    def list_templates(self) -> list[dict[str, Any]]:
        """List all available templates."""
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a template."""
```

## Providers

```python
from henchman.providers import (
    ModelProvider,
    Message,
    ToolCall,
    ToolDeclaration,
    StreamChunk,
    FinishReason,
    DeepSeekProvider,
    OpenAICompatibleProvider,
    AnthropicProvider,
    OllamaProvider,
    OpenRouterProvider,
    ProviderRegistry,
    get_default_registry,
)
```

### ModelProvider

Abstract base class for LLM providers.

```python
class ModelProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
    
    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Stream chat completion responses."""
```

### Message

```python
@dataclass
class Message:
    role: str  # "user", "assistant", "system", "tool"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
```

### StreamChunk

```python
@dataclass
class StreamChunk:
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: FinishReason | None = None
```

### FinishReason

```python
class FinishReason(Enum):
    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
```

### ProviderRegistry

```python
class ProviderRegistry:
    def register(self, name: str, provider_class: type[ModelProvider]) -> None:
        """Register a provider class."""
    
    def create(
        self,
        name: str,
        **kwargs: Any
    ) -> ModelProvider:
        """Create a provider instance."""
    
    def list_providers(self) -> list[str]:
        """List all registered provider names."""
```

### get_default_registry

```python
def get_default_registry() -> ProviderRegistry:
    """Get the default provider registry with all built-in providers."""
```

### Concrete Providers

```python
# DeepSeek (OpenAI-compatible)
provider = DeepSeekProvider(
    api_key="...",
    model="deepseek-chat"
)

# OpenAI-compatible (DeepSeek, OpenAI, Together, Groq, etc.)
provider = OpenAICompatibleProvider(
    api_key="...",
    model="gpt-4",
    base_url="https://api.openai.com/v1"  # Optional: custom endpoint
)

# Anthropic Claude
provider = AnthropicProvider(
    api_key="...",
    model="claude-3-opus-20240229"
)

# Ollama (local models)
provider = OllamaProvider(
    model="llama3.2"  # No API key required
)

# OpenRouter
provider = OpenRouterProvider(
    api_key="...",
    model="openai/gpt-4"
)
```

## Tools

```python
from henchman.tools import (
    Tool,
    ToolKind,
    ToolResult,
    ToolRegistry,
    ConfirmationRequest,
)
```

### Tool

Abstract base class for tools.

```python
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
    
    @property
    @abstractmethod
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
    
    @property
    @abstractmethod
    def kind(self) -> ToolKind:
        """Tool kind (READ, WRITE, EXECUTE, NETWORK)."""
    
    @abstractmethod
    async def execute(self, **params: object) -> ToolResult:
        """Execute the tool."""
```

### ToolKind

```python
class ToolKind(Enum):
    READ = "read"      # Read-only operations (auto-approved)
    WRITE = "write"    # File/database writes (requires confirmation)
    EXECUTE = "execute"  # Shell/process execution (requires confirmation)
    NETWORK = "network"  # Network requests (requires confirmation)
```

### ToolResult

```python
@dataclass
class ToolResult:
    content: str
    success: bool = True
    error: str | None = None
```

### ConfirmationRequest

```python
@dataclass
class ConfirmationRequest:
    tool_name: str
    arguments: dict[str, Any]
    tool_kind: ToolKind
    description: str
```

### ToolRegistry

```python
class ToolRegistry:
    def register(self, tool: Tool) -> None:
        """Register a tool."""
    
    def get_declarations(self) -> list[ToolDeclaration]:
        """Get tool declarations for LLM."""
    
    async def execute(
        self,
        name: str,
        arguments: dict[str, Any]
    ) -> ToolResult:
        """Execute a tool by name."""
    
    def set_confirmation_handler(
        self,
        handler: Callable[[ConfirmationRequest], Awaitable[bool]]
    ) -> None:
        """Set handler for tool confirmation requests."""
    
    def add_auto_approve_policy(self, tool_name: str) -> None:
        """Add a tool to auto-approve list (bypasses confirmation)."""
```

## Configuration

```python
from henchman.config import (
    load_settings,
    Settings,
    ContextLoader,
    ContextSettings,
    ProviderSettings,
    ToolSettings,
    UISettings,
    RagSettings,
    McpServerConfig,
    EnvironmentContext,
    ConfigError,
    DEFAULT_FILENAMES,
    deep_merge,
    format_environment_block,
    gather_environment,
)
```

### load_settings

```python
def load_settings() -> Settings:
    """Load settings from all sources (defaults, user, workspace, env)."""
```

### Settings

```python
@dataclass
class Settings:
    providers: ProviderSettings
    tools: ToolSettings
    ui: UISettings
    context: ContextSettings
    rag: RagSettings
    mcp_servers: dict[str, McpServerConfig]
```

### ContextLoader

```python
class ContextLoader:
    def __init__(
        self,
        filename: str = "HENCHMAN.md",
        include_subdirs: bool = False
    ) -> None:
        """Initialize context loader."""
    
    def discover_files(self) -> list[Path]:
        """Discover context files."""
    
    def load(self) -> str:
        """Load and concatenate context files."""
```

### McpServerConfig

```python
@dataclass
class McpServerConfig:
    command: str
    args: list[str]
    env: dict[str, str] | None = None
    trusted: bool = False
```

### EnvironmentContext

```python
@dataclass
class EnvironmentContext:
    python_version: str
    virtualenv: str | None
    project_type: str
    installed_packages: dict[str, str]
    environment_variables: dict[str, str]
    sys_path: list[str]
```

## CLI

```python
from henchman.cli import (
    Repl,
    ReplConfig,
    OutputRenderer,
    Theme,
    ThemeManager,
    InputHandler,
    get_default_theme,
    expand_at_references,
    is_shell_command,
    is_slash_command,
    parse_shell_command,
)
```

### Repl

```python
class Repl:
    def __init__(
        self,
        provider: ModelProvider,
        console: Console | None = None,
        config: ReplConfig | None = None
    ) -> None:
        """Initialize the REPL."""
    
    async def run(self) -> None:
        """Run the main REPL loop."""
    
    async def process_input(self, user_input: str) -> bool:
        """Process a single user input."""
```

### ReplConfig

```python
@dataclass
class ReplConfig:
    prompt: str = "❯ "
    system_prompt: str = ""
    auto_save: bool = True
    show_welcome: bool = True
    show_goodbye: bool = True
    confirm_tools: bool = True
```

### OutputRenderer

```python
class OutputRenderer:
    def success(self, message: str) -> None:
        """Print success message."""
    
    def info(self, message: str) -> None:
        """Print info message."""
    
    def warning(self, message: str) -> None:
        """Print warning message."""
    
    def error(self, message: str) -> None:
        """Print error message."""
    
    def muted(self, text: str) -> None:
        """Print muted text."""
    
    def heading(self, text: str) -> None:
        """Print heading."""
    
    def markdown(self, content: str) -> None:
        """Render markdown content."""
    
    def code(self, code: str, language: str = "python") -> None:
        """Render code block."""
    
    def tool_call(self, name: str, arguments: dict[str, Any]) -> None:
        """Render tool call."""
    
    def tool_result(self, content: str, success: bool = True, error: str | None = None) -> None:
        """Render tool result."""
```

### InputHandler

```python
class InputHandler:
    async def get_input(self, prompt: str = "❯ ") -> str:
        """Get user input with history and completion."""
    
    async def expand_references(self, text: str) -> str:
        """Expand @file references in text."""
```

### ThemeManager

```python
class ThemeManager:
    def set_theme(self, theme: Theme) -> None:
        """Set the current theme."""
    
    def register_theme(self, name: str, theme: Theme) -> None:
        """Register a custom theme."""
    
    def get_theme(self, name: str) -> Theme | None:
        """Get a theme by name."""
```
