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
    max_tokens: int = 0  # 0 means auto-detect from model
    model: str | None = None
    summarize_dropped: bool = True
    base_tool_iterations: int = 25
    max_protected_ratio: float = 0.3
    intelligent_context: bool = False
    importance_threshold: float = 0.5
    cluster_similarity_threshold: float = 0.7
    adaptive_compression: bool = True
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

## Agents (Multi-Agent Dev Team)

```python
from henchman.agents import (
    AgentConfig,
    AgentIdentity,
    AgentPool,
    Orchestrator,
    CompletionStatus,
    TaskLedger,
    DelegationRecord,
    DelegationStatus,
    ChecklistItem,
)
```

### Orchestrator

```python
class Orchestrator:
    def __init__(
        self,
        provider: ModelProvider,
        tools: list[ToolDeclaration] | None = None,
        config: AgentConfig | None = None
    ) -> None:
        """Initialize the orchestrator."""
    
    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the orchestrator with user input."""
    
    async def run_direct(self, role: str, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run a specific agent role directly."""
    
    def get_metrics_report(self) -> dict[str, Any]:
        """Get performance metrics report."""
    
    def get_pool(self) -> AgentPool:
        """Get the agent pool."""
    
    def get_event_bus(self) -> EventBus:
        """Get the event bus."""
```

### AgentPool

```python
class AgentPool:
    def get_agent(self, role: str) -> Agent:
        """Get an agent by role."""
    
    def list_agents(self) -> list[str]:
        """List all available agent roles."""
    
    def register_agent(self, role: str, agent: Agent) -> None:
        """Register an agent for a role."""
```

### AgentIdentity

```python
@dataclass
class AgentIdentity:
    id: str
    name: str
    role: str
    description: str
    capabilities: list[str]
```

### TaskLedger

```python
class TaskLedger:
    def add_delegation(self, record: DelegationRecord) -> None:
        """Add a delegation record."""
    
    def update_status(self, delegation_id: str, status: DelegationStatus) -> None:
        """Update delegation status."""
    
    def get_delegations(self) -> list[DelegationRecord]:
        """Get all delegation records."""
```

## Extensions

```python
from henchman.extensions import (
    Extension,
    ExtensionManager,
    PluginManager,
    PluginMetadata,
    PluginInstallation,
    PluginSource,
    PluginCompatibility,
    PluginPermission,
    PluginSearchResult,
    PluginStats,
    PluginUpdateInfo,
    SecurityReport,
)
```

### Extension

```python
class Extension(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Extension name."""
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Extension version."""
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Extension description."""
    
    def get_tools(self) -> list[Tool]:
        """Get tools provided by this extension."""
    
    def get_commands(self) -> list[Command]:
        """Get commands provided by this extension."""
    
    def get_context(self) -> str:
        """Get context provided by this extension."""
```

### ExtensionManager

```python
class ExtensionManager:
    def discover_entry_points(self) -> None:
        """Discover extensions from installed packages."""
    
    def discover_directory(self, path: Path) -> None:
        """Discover extensions from directory."""
    
    def load_extension(self, name: str) -> Extension:
        """Load an extension by name."""
    
    def list_extensions(self) -> list[str]:
        """List all loaded extensions."""
```

### PluginManager

```python
class PluginManager:
    async def search(self, query: str) -> list[PluginSearchResult]:
        """Search for plugins."""
    
    async def install(self, plugin_id: str) -> PluginInstallation:
        """Install a plugin."""
    
    async def uninstall(self, plugin_id: str) -> bool:
        """Uninstall a plugin."""
    
    async def update(self, plugin_id: str) -> PluginUpdateInfo:
        """Update a plugin."""
    
    async def check_security(self, plugin_id: str) -> SecurityReport:
        """Check plugin security."""
```

## MCP (Model Context Protocol)

```python
from henchman.mcp import (
    McpClient,
    McpManager,
    McpServerConfig,
    McpTool,
    McpToolDefinition,
    McpToolResult,
)
```

### McpClient

```python
class McpClient:
    def __init__(self, name: str, config: McpServerConfig) -> None:
        """Initialize MCP client."""
    
    async def connect(self) -> None:
        """Connect to the MCP server."""
    
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
    
    async def discover_tools(self) -> list[McpToolDefinition]:
        """Discover tools from the server."""
    
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        """Call a tool on the server."""
```

### McpManager

```python
class McpManager:
    def __init__(self, configs: dict[str, McpServerConfig]) -> None:
        """Initialize MCP manager with server configurations."""
    
    async def connect_all(self) -> None:
        """Connect to all configured servers."""
    
    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
    
    def get_all_tools(self) -> list[McpTool]:
        """Get all tools from all connected servers."""
    
    def get_client(self, name: str) -> McpClient | None:
        """Get a client by name."""
```

### McpTool

```python
class McpTool(Tool):
    """Wrapper for MCP tools as internal Tool instances."""
```

## RAG (Retrieval-Augmented Generation)

```python
from henchman.rag import (
    CodeChunker,
    Embedder,
    RepositoryIdentifier,
)
```

### CodeChunker

```python
class CodeChunker:
    def chunk_file(self, path: Path, content: str) -> list[dict[str, Any]]:
        """Chunk a code file into semantic segments."""
    
    def chunk_directory(self, directory: Path) -> list[dict[str, Any]]:
        """Chunk all files in a directory."""
```

### Embedder

```python
class Embedder:
    async def embed(self, text: str) -> list[float]:
        """Generate embeddings for text."""
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
```

## Knowledge Graph

```python
from henchman.knowledge import (
    KnowledgeGraph,
    Entity,
    Relation,
    EntityType,
    RelationType,
)
```

### KnowledgeGraph

```python
class KnowledgeGraph:
    def add_entity(self, entity: Entity) -> None:
        """Add an entity to the graph."""
    
    def add_relation(self, relation: Relation) -> None:
        """Add a relation to the graph."""
    
    def query(self, query: str, entity_type: EntityType | None = None) -> list[Entity]:
        """Query the knowledge graph."""
    
    def get_neighbors(self, entity_id: str, depth: int = 1) -> list[Entity]:
        """Get neighboring entities."""
```

## Metrics

```python
from henchman.metrics import (
    MetricsStorage,
    PerformanceMetrics,
    QualityMetrics,
    ToolMetrics,
    OrchestratorMetrics,
    MetricsExporter,
)
```

### MetricsStorage

```python
class MetricsStorage:
    def store_metric(self, metric: dict[str, Any]) -> None:
        """Store a metric."""
    
    def query_metrics(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """Query metrics with filters."""
    
    def clear_metrics(self) -> None:
        """Clear all metrics."""
```

### MetricsExporter

```python
class MetricsExporter:
    def export_to_json(self, filepath: str, **filters: Any) -> None:
        """Export metrics to JSON file."""
    
    def export_to_csv(self, filepath: str, **filters: Any) -> None:
        """Export metrics to CSV file."""
    
    def export_to_prometheus(self, endpoint: str, **filters: Any) -> None:
        """Export metrics to Prometheus endpoint."""
    
    def export_summary(self, **filters: Any) -> dict[str, Any]:
        """Export summary statistics."""
    
    def get_available_formats(self) -> list[str]:
        """Get list of available export formats."""
```

## Utilities

```python
from henchman.utils import (
    TokenCounter,
    IntelligentContextManager,
    ContextCompactor,
    MessageClusterer,
    ImportanceScorer,
    RetryManager,
    validate_message_sequence,
    repair_message_sequence,
    is_valid_message_sequence,
    format_message_sequence_for_debug,
)
```

### TokenCounter

```python
class TokenCounter:
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
    
    def count_messages(self, messages: list[Message]) -> int:
        """Count tokens in messages."""
```

### IntelligentContextManager

```python
class IntelligentContextManager:
    def compact(
        self,
        messages: list[Message],
        protect_from_index: int = 0
    ) -> list[Message]:
        """Compact messages using intelligent strategies."""
```

### RetryManager

```python
class RetryManager:
    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[T]],
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0
    ) -> T:
        """Execute a function with retry logic."""
```
