# API Reference

This page provides API reference for the main Henchman-AI modules.

## Core

### Agent

```python
from henchman.core import Agent, AgentEvent, EventType
```

#### Agent

The main agent class that orchestrates LLM interactions.

```python
class Agent:
    def __init__(
        self,
        provider: ModelProvider,
        tools: list[ToolDeclaration] | None = None,
        system_prompt: str = ""
    ) -> None:
        """Initialize the agent."""
    
    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the agent with user input, yielding events."""
    
    def submit_tool_result(self, tool_call_id: str, result: str) -> None:
        """Submit a tool result for a pending tool call."""
    
    def clear_history(self) -> None:
        """Clear conversation history."""
```

#### EventType

```python
class EventType(Enum):
    CONTENT = "content"        # Text content from LLM
    THOUGHT = "thought"        # Thinking/reasoning
    TOOL_CALL_REQUEST = "tool_call_request"
    TOOL_CALL_RESULT = "tool_call_result"
    ERROR = "error"
    FINISHED = "finished"
```

#### AgentEvent

```python
@dataclass
class AgentEvent:
    type: EventType
    data: Any
```

### Session

```python
from henchman.core import Session, SessionManager, SessionMessage
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

### Concrete Providers

```python
from henchman.providers import (
    DeepSeekProvider,
    OpenAICompatibleProvider,
    AnthropicProvider,
    OllamaProvider,
)

# DeepSeek
provider = DeepSeekProvider(
    api_key="...",
    model="deepseek-chat"
)

# Anthropic
provider = AnthropicProvider(
    api_key="...",
    model="claude-3-opus-20240229"
)
```

## Tools

```python
from henchman.tools import (
    Tool,
    ToolKind,
    ToolResult,
    ToolRegistry,
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

### ToolResult

```python
@dataclass
class ToolResult:
    content: str
    success: bool = True
    error: str | None = None
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
```

## Configuration

```python
from henchman.config import load_settings, Settings, ContextLoader
```

### load_settings

```python
def load_settings() -> Settings:
    """Load settings from all sources."""
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

## CLI

```python
from henchman.cli import Repl, ReplConfig, OutputRenderer
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
```
