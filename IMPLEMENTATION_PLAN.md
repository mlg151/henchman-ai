# MLG-CLI Implementation Plan

> **A Model-Agnostic AI Agent CLI in Python**  
> Inspired by gemini-cli, built for extensibility  
> Primary Target: DeepSeek API (OpenAI-compatible)  
> **Created:** January 23, 2026

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Phase 1: Project Foundation](#phase-1-project-foundation)
4. [Phase 2: Provider System](#phase-2-provider-system)
5. [Phase 3: Core Agent Loop](#phase-3-core-agent-loop)
6. [Phase 4: Tool System](#phase-4-tool-system)
7. [Phase 5: Built-in Tools](#phase-5-built-in-tools)
8. [Phase 6: Configuration System](#phase-6-configuration-system)
9. [Phase 7: Terminal UI](#phase-7-terminal-ui)
10. [Phase 8: Session Management](#phase-8-session-management)
11. [Phase 9: MCP Integration](#phase-9-mcp-integration)
12. [Phase 10: Extensions & Plugins](#phase-10-extensions--plugins)
13. [Phase 11: Advanced Features](#phase-11-advanced-features)
14. [Phase 12: Polish & Release](#phase-12-polish--release)
15. [Technical Reference](#technical-reference)

---

## Executive Summary

### Goal

Build a Python CLI agent that recreates gemini-cli functionality while being:

| Principle | Description |
|-----------|-------------|
| 🔄 **Model-Agnostic** | Support any LLM: DeepSeek, OpenAI, Anthropic, Ollama, etc. |
| 🐍 **Pythonic** | Leverage Python's async ecosystem and rich libraries |
| 🔌 **Extensible** | Plugin system for tools, providers, and commands |
| 🚀 **Production-Ready** | Proper error handling, testing, and packaging |

### Key Insight: DeepSeek = OpenAI Compatible

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-key",
    base_url="https://api.deepseek.com"  # Just change this!
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[...],
    tools=[...],  # Function calling works!
    stream=True
)
```

**One provider implementation handles**: DeepSeek, OpenAI, Together, Groq, Fireworks, and any OpenAI-compatible API.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           User Terminal                              │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                      mlg/cli/ (UI Layer)                             │
│  • InputHandler (prompt_toolkit)    • OutputRenderer (rich)          │
│  • CommandParser (/commands)        • ThemeManager                   │
│  • ConfirmationDialogs              • StatusBar                      │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                     mlg/core/ (Agent Layer)                          │
│  • AgentLoop (async generator)      • EventBus (typed events)        │
│  • ToolRegistry                     • PolicyEngine                   │
│  • SessionManager                   • ContextLoader (MLG.md)         │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
┌────────▼────────┐  ┌────────▼────────┐  ┌───────▼────────┐
│  mlg/providers/ │  │   mlg/tools/    │  │   mlg/mcp/     │
│  ┌───────────┐  │  │  ┌───────────┐  │  │ ┌───────────┐  │
│  │ OpenAI    │  │  │  │ ReadFile  │  │  │ │McpManager │  │
│  │ Compatible│──┼──│  │ WriteFile │  │  │ │McpClient  │  │
│  │ (DeepSeek)│  │  │  │ Shell     │  │  │ │McpTool    │  │
│  │ Anthropic │  │  │  │ WebFetch  │  │  │ └───────────┘  │
│  │ Ollama    │  │  │  │ Grep/Glob │  │  └────────────────┘
│  └───────────┘  │  │  └───────────┘  │
└─────────────────┘  └─────────────────┘
```

---

## Phase 1: Project Foundation ✅

**Goal**: Set up project structure and dependencies

**Status**: COMPLETE (2026-01-23)

### Tasks

- [x] **1.1** Create project directory structure
- [x] **1.2** Initialize `pyproject.toml` with dependencies
- [x] **1.3** Set up development tooling (ruff, mypy, pytest)
- [x] **1.4** Create basic `__main__.py` entry point
- [x] **1.5** Add README and LICENSE

### Directory Structure

```
mlg-cli/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── mlg/
│       ├── __init__.py
│       ├── __main__.py          # python -m mlg
│       ├── version.py
│       ├── cli/                 # UI Layer
│       ├── core/                # Agent Layer  
│       ├── providers/           # Model Providers
│       ├── tools/               # Built-in Tools
│       ├── mcp/                 # MCP Integration
│       ├── config/              # Configuration
│       └── utils/               # Utilities
├── tests/
└── docs/
```

### Dependencies

```toml
[project]
name = "mlg-cli"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "openai>=1.40",
    "pydantic>=2.0",
    "rich>=13.0",
    "prompt-toolkit>=3.0",
    "anyio>=4.0",
    "click>=8.0",
    "pyyaml>=6.0",
]

[project.scripts]
mlg = "mlg.cli.app:main"
```

### Acceptance Criteria

- `pip install -e .` works
- `mlg --version` prints version
- `mlg --help` shows help text
- All linting passes

---

## Phase 2: Provider System ✅

**Goal**: Abstract model providers with DeepSeek as primary target

**Status**: COMPLETE (2026-01-23)

### Tasks

- [x] **2.1** Define `ModelProvider` protocol/ABC
- [x] **2.2** Define message and streaming types
- [x] **2.3** Implement `OpenAICompatibleProvider` base class
- [x] **2.4** Implement `DeepSeekProvider` (extends OpenAI-compatible)
- [x] **2.5** Create provider registry for discovery
- [x] **2.6** Add unit tests for providers (100% coverage)

### Core Types

```python
# mlg/providers/base.py

@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class ToolDeclaration:
    name: str
    description: str
    parameters: dict  # JSON Schema

@dataclass
class StreamChunk:
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: FinishReason | None = None
    thinking: str | None = None  # For reasoning models

class ModelProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...
    
    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs
    ) -> AsyncIterator[StreamChunk]: ...
```

### DeepSeek Implementation

```python
# mlg/providers/deepseek.py

class DeepSeekProvider(OpenAICompatibleProvider):
    name = "deepseek"
    
    def __init__(self, api_key: str | None = None, model: str = "deepseek-chat"):
        super().__init__(
            api_key=api_key or os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com",
            default_model=model,
        )
    
    async def list_models(self) -> list[str]:
        return ["deepseek-chat", "deepseek-reasoner"]
```

### Acceptance Criteria

- Can instantiate DeepSeek provider
- Can stream a simple chat completion
- Tool declarations are properly formatted
- Provider works with/without API key env var

---

## Phase 3: Core Agent Loop

**Goal**: Implement the main agent orchestration with event streaming

### Tasks

- [ ] **3.1** Define event types (`AgentEvent`, `EventType`)
- [ ] **3.2** Implement basic `Agent` class
- [ ] **3.3** Implement streaming with async generators
- [ ] **3.4** Add conversation history management
- [ ] **3.5** Implement tool call detection and routing
- [ ] **3.6** Add unit tests for agent loop

### Event Types

```python
# mlg/core/events.py

class EventType(Enum):
    CONTENT = auto()           # Text from model
    THOUGHT = auto()           # Reasoning content
    TOOL_CALL_REQUEST = auto() # Model wants a tool
    TOOL_CALL_RESULT = auto()  # Tool execution result
    TOOL_CONFIRMATION = auto() # Awaiting user approval
    ERROR = auto()
    FINISHED = auto()

@dataclass
class AgentEvent:
    type: EventType
    data: Any = None
```

### Agent Implementation

```python
# mlg/core/agent.py

class Agent:
    def __init__(
        self,
        provider: ModelProvider,
        tool_registry: ToolRegistry,
        system_prompt: str = "",
    ):
        self.provider = provider
        self.tools = tool_registry
        self.history: list[Message] = []
    
    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Main agent loop - yields events as they occur"""
        self.history.append(Message(role="user", content=user_input))
        
        while True:
            # Stream from model
            async for chunk in self.provider.chat_completion_stream(
                messages=self.history,
                tools=self.tools.get_declarations(),
            ):
                if chunk.content:
                    yield AgentEvent(EventType.CONTENT, chunk.content)
                if chunk.tool_calls:
                    # Handle tool calls...
                    pass
            
            # If no tool calls, we're done
            if not pending_tool_calls:
                yield AgentEvent(EventType.FINISHED)
                break
```

### Acceptance Criteria

- Agent streams text responses
- Agent detects tool call requests
- History is maintained across turns
- Can handle multi-turn tool execution

---

## Phase 4: Tool System

**Goal**: Implement extensible tool framework with confirmation policies

### Tasks

- [ ] **4.1** Define `Tool` base class
- [ ] **4.2** Define `ToolResult` and `ConfirmationRequest` types
- [ ] **4.3** Implement `ToolRegistry` for tool management
- [ ] **4.4** Implement tool confirmation flow
- [ ] **4.5** Implement `PolicyEngine` for auto-approval rules
- [ ] **4.6** Add unit tests

### Tool Base Class

```python
# mlg/tools/base.py

class ToolKind(Enum):
    READ = "read"       # Auto-approve (read_file, ls, glob)
    WRITE = "write"     # Requires confirmation (write_file, edit)
    EXECUTE = "execute" # Requires confirmation (shell)
    NETWORK = "network" # Requires confirmation (web_fetch)

@dataclass
class ToolResult:
    content: str           # Content for model
    success: bool = True
    display: str | None = None  # Different display for user
    error: str | None = None

class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...
    
    @property
    @abstractmethod
    def description(self) -> str: ...
    
    @property
    @abstractmethod
    def parameters(self) -> dict: ...  # JSON Schema
    
    @property
    def kind(self) -> ToolKind:
        return ToolKind.OTHER
    
    def needs_confirmation(self, params: dict) -> ConfirmationRequest | None:
        """Return confirmation request if needed"""
        if self.kind in (ToolKind.WRITE, ToolKind.EXECUTE):
            return ConfirmationRequest(...)
        return None
    
    @abstractmethod
    async def execute(self, **params) -> ToolResult: ...
```

### Tool Registry

```python
# mlg/tools/registry.py

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._confirmation_handler: Callable | None = None
    
    def register(self, tool: Tool) -> None: ...
    def get_declarations(self) -> list[ToolDeclaration]: ...
    async def execute(self, name: str, params: dict) -> ToolResult: ...
```

### Acceptance Criteria

- Can register and list tools
- Tool declarations generated correctly
- Confirmation flow works for write/execute tools
- Read tools auto-approved

---

## Phase 5: Built-in Tools

**Goal**: Implement core tools matching gemini-cli functionality

### Tasks

- [ ] **5.1** `read_file` - Read file contents with line ranges
- [ ] **5.2** `write_file` - Create/overwrite files
- [ ] **5.3** `edit_file` - Precise text replacements
- [ ] **5.4** `ls` - List directory contents
- [ ] **5.5** `glob` - Pattern-based file search
- [ ] **5.6** `grep` - Text/regex search in files
- [ ] **5.7** `shell` - Execute shell commands
- [ ] **5.8** `web_fetch` - Fetch URL contents
- [ ] **5.9** `ask_user` - Request user input
- [ ] **5.10** Add tests for each tool

### Example: ReadFile Tool

```python
# mlg/tools/file_read.py

class ReadFileTool(Tool):
    name = "read_file"
    description = "Read contents of a file"
    kind = ToolKind.READ
    
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "start_line": {"type": "integer", "default": 1},
            "end_line": {"type": "integer", "default": -1},
        },
        "required": ["path"]
    }
    
    async def execute(self, path: str, start_line: int = 1, end_line: int = -1) -> ToolResult:
        try:
            content = Path(path).read_text()
            lines = content.splitlines()[start_line-1:end_line if end_line > 0 else None]
            return ToolResult(content="\n".join(lines), success=True)
        except Exception as e:
            return ToolResult(content=f"Error: {e}", success=False, error=str(e))
```

### Example: Shell Tool

```python
# mlg/tools/shell.py

class ShellTool(Tool):
    name = "run_shell_command"
    description = "Execute a shell command"
    kind = ToolKind.EXECUTE
    
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer", "default": 60},
        },
        "required": ["command"]
    }
    
    async def execute(self, command: str, timeout: int = 60) -> ToolResult:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "MLG_CLI": "1"},
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        return ToolResult(
            content=f"Exit: {process.returncode}\n{stdout.decode()}{stderr.decode()}",
            success=process.returncode == 0,
        )
```

### Acceptance Criteria

- All tools execute correctly
- Error handling is robust
- Tools respect workspace boundaries
- Shell tool sets `MLG_CLI=1` env var

---

## Phase 6: Configuration System

**Goal**: Hierarchical settings with YAML/JSON support

### Tasks

- [ ] **6.1** Define settings schema with Pydantic
- [ ] **6.2** Implement settings file discovery
- [ ] **6.3** Implement hierarchical merging
- [ ] **6.4** Add environment variable overrides
- [ ] **6.5** Implement context file (MLG.md) loading
- [ ] **6.6** Add settings validation

### Settings Schema

```python
# mlg/config/schema.py

class ProviderSettings(BaseModel):
    default: str = "deepseek"
    deepseek: dict = Field(default_factory=lambda: {"model": "deepseek-chat"})
    openai: dict = Field(default_factory=dict)
    anthropic: dict = Field(default_factory=dict)
    ollama: dict = Field(default_factory=lambda: {"base_url": "http://localhost:11434"})

class ToolSettings(BaseModel):
    auto_accept_read: bool = True
    shell_timeout: int = 60
    sandbox: Literal["none", "docker"] = "none"

class UISettings(BaseModel):
    theme: str = "dark"
    show_line_numbers: bool = True

class Settings(BaseModel):
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    ui: UISettings = Field(default_factory=UISettings)
    mcp_servers: dict[str, McpServerConfig] = Field(default_factory=dict)
```

### Settings Loading

```python
# mlg/config/settings.py

def load_settings() -> Settings:
    """Load settings with precedence: defaults < user < workspace < env"""
    settings = {}
    
    # User settings
    user_path = Path.home() / ".mlg" / "settings.yaml"
    if user_path.exists():
        settings = deep_merge(settings, yaml.safe_load(user_path.read_text()))
    
    # Workspace settings
    workspace_path = Path.cwd() / ".mlg" / "settings.yaml"
    if workspace_path.exists():
        settings = deep_merge(settings, yaml.safe_load(workspace_path.read_text()))
    
    # Environment overrides
    if provider := os.environ.get("MLG_PROVIDER"):
        settings.setdefault("providers", {})["default"] = provider
    
    return Settings(**settings)
```

### Context Loading (MLG.md)

```python
# mlg/core/context.py

class ContextLoader:
    FILENAME = "MLG.md"
    
    def discover_files(self) -> list[Path]:
        """Find all MLG.md files in hierarchy"""
        files = []
        # Global: ~/.mlg/MLG.md
        # Ancestors: walk up to git root
        # Subdirectories: walk down respecting .gitignore
        return files
    
    def load(self) -> str:
        """Concatenate all context files"""
        return "\n\n---\n\n".join(
            f"# Context: {f}\n{f.read_text()}" 
            for f in self.discover_files()
        )
```

### Acceptance Criteria

- Settings load from correct locations
- Merge precedence works correctly
- Env vars override file settings
- MLG.md files discovered and concatenated

---

## Phase 7: Terminal UI

**Goal**: Rich terminal interface with streaming output

### Tasks

- [ ] **7.1** Set up Rich console and themes
- [ ] **7.2** Implement input handling with prompt_toolkit
- [ ] **7.3** Implement streaming markdown output
- [ ] **7.4** Implement tool confirmation dialogs
- [ ] **7.5** Add status bar with context info
- [ ] **7.6** Implement slash command parsing
- [ ] **7.7** Implement at-command (@file) parsing
- [ ] **7.8** Implement shell mode (!)

### Main CLI Loop

```python
# mlg/cli/app.py

async def run_cli():
    console = Console()
    settings = load_settings()
    provider = create_provider(settings)
    tools = create_tool_registry(settings)
    agent = Agent(provider, tools, system_prompt=load_context())
    
    session = PromptSession(history=FileHistory(".mlg_history"))
    
    console.print("[bold blue]MLG CLI[/] - /help for commands, /quit to exit\n")
    
    while True:
        try:
            user_input = await asyncio.to_thread(session.prompt, "❯ ")
            
            # Handle commands
            if user_input.startswith("/"):
                await handle_slash_command(user_input, console)
                continue
            if user_input.startswith("!"):
                await handle_shell_command(user_input, console)
                continue
            
            # Expand @file references
            user_input = await expand_at_references(user_input)
            
            # Run agent
            async for event in agent.run(user_input):
                await render_event(event, console)
                
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted[/]")
        except EOFError:
            break
```

### Slash Commands

```python
# mlg/cli/commands/

/help      - Show help
/quit      - Exit CLI
/model     - Select model
/provider  - Select provider
/settings  - Open settings
/chat save/resume/list - Session management
/memory show/refresh   - Context management
/tools     - List available tools
/clear     - Clear screen
```

### Acceptance Criteria

- Streaming output renders smoothly
- Markdown syntax highlighting works
- Tool confirmations show clearly
- Commands parse correctly
- @file references expand inline

---

## Phase 8: Session Management

**Goal**: Save and restore conversation sessions

### Tasks

- [ ] **8.1** Define session data model
- [ ] **8.2** Implement session persistence (JSON)
- [ ] **8.3** Implement `/chat save <tag>`
- [ ] **8.4** Implement `/chat resume <tag>`
- [ ] **8.5** Implement `/chat list`
- [ ] **8.6** Add auto-save on exit

### Session Model

```python
# mlg/core/session.py

@dataclass
class Session:
    id: str
    project_hash: str
    started: str
    last_updated: str
    messages: list[SessionMessage]
    
class SessionManager:
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or (Path.home() / ".mlg" / "sessions")
    
    def save(self, tag: str | None = None) -> Path: ...
    def load(self, session_id: str) -> Session: ...
    def list_sessions(self, project_hash: str) -> list[Session]: ...
```

### Acceptance Criteria

- Sessions save with all messages
- Sessions restore history correctly
- Project-scoped session listing
- Auto-save on graceful exit

---

## Phase 9: MCP Integration

**Goal**: Support Model Context Protocol servers

### Tasks

- [ ] **9.1** Add `mcp` package dependency
- [ ] **9.2** Implement `McpClient` for single server
- [ ] **9.3** Implement `McpManager` for multiple servers
- [ ] **9.4** Implement `McpTool` wrapper as internal Tool
- [ ] **9.5** Add MCP server configuration
- [ ] **9.6** Implement `/mcp list/refresh` commands

### MCP Configuration

```yaml
# ~/.mlg/settings.yaml
mcp_servers:
  filesystem:
    command: npx
    args: ["@anthropic-ai/mcp-filesystem-server", "/home/user"]
    trusted: false
  
  github:
    command: uvx
    args: ["mcp-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    trusted: true
```

### MCP Client

```python
# mlg/mcp/client.py

class McpClient:
    def __init__(self, name: str, config: McpServerConfig):
        self.name = name
        self.config = config
    
    async def connect(self) -> None:
        """Connect via stdio transport"""
        ...
    
    async def discover_tools(self) -> list[McpTool]:
        """Get tools from server"""
        ...
    
    async def call_tool(self, name: str, args: dict) -> Any:
        """Execute tool on server"""
        ...
```

### Acceptance Criteria

- Can connect to MCP servers
- Tools discovered and registered
- Tool execution works through MCP
- Trusted servers skip confirmation

---

## Phase 10: Extensions & Plugins

**Goal**: Allow third-party extensions

### Tasks

- [ ] **10.1** Define `Extension` base class
- [ ] **10.2** Implement entry point discovery
- [ ] **10.3** Implement directory-based extensions
- [ ] **10.4** Create extension loading system
- [ ] **10.5** Implement `/extensions` command

### Extension Interface

```python
# mlg/extensions/base.py

class Extension(ABC):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    
    def get_tools(self) -> list[Tool]:
        """Return tools provided by this extension"""
        return []
    
    def get_commands(self) -> list[Command]:
        """Return slash commands"""
        return []
    
    def get_context(self) -> str:
        """Additional system prompt context"""
        return ""
```

### Extension Discovery

```python
# Entry points in pyproject.toml
[project.entry-points."mlg.extensions"]
my_extension = "my_package:MyExtension"

# Directory-based
~/.mlg/extensions/my-ext/extension.py
```

### Acceptance Criteria

- Entry point extensions load
- Directory extensions load
- Extension tools register correctly
- Extension commands work

---

## Phase 11: Advanced Features

**Goal**: Implement remaining gemini-cli features

### Tasks

- [ ] **11.1** Checkpointing (file state snapshots before edits)
- [ ] **11.2** Sandboxing (Docker container execution)
- [ ] **11.3** Hooks system (before/after events)
- [ ] **11.4** Headless mode (`--prompt` flag)
- [ ] **11.5** JSON output mode (`--output-format json`)
- [ ] **11.6** Multiple providers (Anthropic, Ollama)

### Headless Mode

```bash
# Simple prompt
mlg --prompt "Explain this code" < file.py

# JSON output for scripting
mlg -p "Summarize README.md" --output-format json

# Streaming JSON for real-time
mlg -p "Run tests" --output-format stream-json
```

### Hooks System

```python
# ~/.mlg/hooks/before_tool/validate.py
# Receives JSON on stdin, outputs JSON on stdout
# Exit 0 = allow, Exit 2 = block

class HookRunner:
    async def run(self, event: HookEvent, data: dict) -> HookResult:
        """Run all hooks for event"""
        ...
```

### Acceptance Criteria

- Checkpoints save/restore file state
- Sandbox executes commands in Docker
- Hooks intercept and can block actions
- Headless mode works for scripting

---

## Phase 12: Polish & Release

**Goal**: Production-ready release

### Tasks

- [ ] **12.1** Comprehensive test suite (>80% coverage)
- [ ] **12.2** Documentation site (mkdocs)
- [ ] **12.3** PyPI packaging and publishing
- [ ] **12.4** GitHub Actions CI/CD
- [ ] **12.5** Multiple theme support
- [ ] **12.6** Performance optimization
- [ ] **12.7** Error handling audit
- [ ] **12.8** Security review

### Documentation

```
docs/
├── index.md           # Overview
├── getting-started.md # Quick start
├── configuration.md   # Settings reference
├── providers.md       # Provider setup
├── tools.md           # Built-in tools
├── mcp.md             # MCP integration
├── extensions.md      # Writing extensions
└── api/               # API reference
```

### CI/CD

```yaml
# .github/workflows/ci.yml
- Lint (ruff)
- Type check (mypy)
- Test (pytest)
- Build
- Publish to PyPI (on tag)
```

### Acceptance Criteria

- All tests pass
- Documentation complete
- Package installable from PyPI
- CI/CD working

---

## Technical Reference

### Async Patterns

```python
# Everything is async generators for streaming
async def agent_loop() -> AsyncIterator[AgentEvent]:
    async for chunk in provider.stream():
        yield AgentEvent(...)

# Use anyio for runtime flexibility
import anyio
await anyio.sleep(1)  # Works with asyncio or trio
```

### Error Handling

```python
# Custom exceptions
class MlgError(Exception): ...
class ProviderError(MlgError): ...
class ToolError(MlgError): ...
class ConfigError(MlgError): ...

# Graceful degradation
try:
    result = await tool.execute(**params)
except ToolError as e:
    return ToolResult(content=f"Error: {e}", success=False)
```

### Testing Strategy

```python
# Mock providers for unit tests
@pytest.fixture
def mock_provider():
    provider = AsyncMock(spec=ModelProvider)
    async def mock_stream(*args, **kwargs):
        yield StreamChunk(content="Hello")
        yield StreamChunk(finish_reason=FinishReason.STOP)
    provider.chat_completion_stream = mock_stream
    return provider

# Integration tests with real API (optional, slow)
@pytest.mark.integration
async def test_deepseek_real():
    provider = DeepSeekProvider()
    ...
```

---

## Timeline Estimate

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Foundation | 2 days | 2 days |
| Phase 2: Providers | 3 days | 5 days |
| Phase 3: Agent Loop | 3 days | 8 days |
| Phase 4: Tool System | 2 days | 10 days |
| Phase 5: Built-in Tools | 4 days | 14 days |
| Phase 6: Configuration | 2 days | 16 days |
| Phase 7: Terminal UI | 4 days | 20 days |
| Phase 8: Sessions | 2 days | 22 days |
| Phase 9: MCP | 3 days | 25 days |
| Phase 10: Extensions | 2 days | 27 days |
| Phase 11: Advanced | 5 days | 32 days |
| Phase 12: Polish | 5 days | 37 days |

**Total: ~7-8 weeks** for full implementation

---

## Open Decisions

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **UI Framework** | Rich only vs Textual TUI | Start with Rich, add Textual later |
| **Async Runtime** | asyncio vs anyio | anyio for flexibility |
| **Context Filename** | MLG.md vs AGENT.md | MLG.md (matches project) |
| **Default Provider** | DeepSeek vs Ollama | DeepSeek (easy API, free tier) |

---

*Document Version: 1.0*  
*Last Updated: January 23, 2026*
