# Henchman-AI Implementation Plan

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
11. [Phase 11: Advanced Features](#phase-11-advanced-features)
12. [Phase 12: Polish & Release](#phase-12-polish--release)
13. [Phase 13: Skills & Learning](#phase-13-skills--learning)
14. [Phase 14: Enhanced Interaction & Context](#phase-14-enhanced-interaction--context)
15. [Phase 15: Reinforced Memory System](#phase-15-reinforced-memory-system)
16. [Technical Reference](#technical-reference)

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
│                      henchman/cli/ (UI Layer)                             │
│  • InputHandler (prompt_toolkit)    • OutputRenderer (rich)          │
│  • CommandParser (/commands)        • ThemeManager                   │
│  • ConfirmationDialogs              • StatusBar                      │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                     henchman/core/ (Agent Layer)                          │
│  • AgentLoop (async generator)      • EventBus (typed events)        │
│  • ToolRegistry                     • PolicyEngine                   │
│  • SessionManager                   • ContextLoader (HENCHMAN.md)         │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
┌────────▼────────┐  ┌────────▼────────┐  ┌───────▼────────┐
│  henchman/providers/ │  │   henchman/tools/    │  │   henchman/mcp/     │
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
henchman-ai/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── henchman/
│       ├── __init__.py
│       ├── __main__.py          # python -m henchman
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
name = "henchman-ai"
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
henchman = "henchman.cli.app:main"
```

### Acceptance Criteria

- `pip install -e .` works
- `henchman --version` prints version
- `henchman --help` shows help text
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
# henchman/providers/base.py

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
# henchman/providers/deepseek.py

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

## Phase 3: Core Agent Loop ✅

**Goal**: Implement the main agent orchestration with event streaming

**Status**: COMPLETE (2026-01-23)

### Tasks

- [x] **3.1** Define event types (`AgentEvent`, `EventType`)
- [x] **3.2** Implement basic `Agent` class
- [x] **3.3** Implement streaming with async generators
- [x] **3.4** Add conversation history management
- [x] **3.5** Implement tool call detection and routing
- [x] **3.6** Add unit tests for agent loop (100% coverage)

### Event Types

```python
# henchman/core/events.py

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
# henchman/core/agent.py

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

## Phase 4: Tool System ✅

**Goal**: Implement extensible tool framework with confirmation policies

**Status**: COMPLETE (2026-01-23)

### Tasks

- [x] **4.1** Define `Tool` base class
- [x] **4.2** Define `ToolResult` and `ConfirmationRequest` types
- [x] **4.3** Implement `ToolRegistry` for tool management
- [x] **4.4** Implement tool confirmation flow
- [x] **4.5** Implement `PolicyEngine` for auto-approval rules
- [x] **4.6** Add unit tests (100% coverage, 126 tests)

### Tool Base Class

```python
# henchman/tools/base.py

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
# henchman/tools/registry.py

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

## Phase 5: Built-in Tools ✅

**Goal**: Implement core tools matching gemini-cli functionality

**Status**: COMPLETE (2026-01-23) - ask_user deferred to UI phase

### Tasks

- [x] **5.1** `read_file` - Read file contents with line ranges
- [x] **5.2** `write_file` - Create/overwrite files
- [x] **5.3** `edit_file` - Precise text replacements
- [x] **5.4** `ls` - List directory contents
- [x] **5.5** `glob` - Pattern-based file search
- [x] **5.6** `grep` - Text/regex search in files
- [x] **5.7** `shell` - Execute shell commands
- [x] **5.8** `web_fetch` - Fetch URL contents
- [x] **5.9** `ask_user` - Request user input (implemented with placeholder for REPL integration)
- [x] **5.10** Add tests for each tool (100% coverage, 214 tests)

### Example: ReadFile Tool

```python
# henchman/tools/file_read.py

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
# henchman/tools/shell.py

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
            env={**os.environ, "HENCHMAN_CLI": "1"},
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
- Shell tool sets `HENCHMAN_CLI=1` env var

---

## Phase 6: Configuration System ✅

**Goal**: Hierarchical settings with YAML/JSON support

**Status**: COMPLETE (2026-01-23)

### Tasks

- [x] **6.1** Define settings schema with Pydantic
- [x] **6.2** Implement settings file discovery
- [x] **6.3** Implement hierarchical merging
- [x] **6.4** Add environment variable overrides
- [x] **6.5** Implement context file (HENCHMAN.md) loading
- [x] **6.6** Add settings validation
- [x] **6.7** Add unit tests (100% coverage, 271 tests)

### Settings Schema

```python
# henchman/config/schema.py

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
# henchman/config/settings.py

def load_settings() -> Settings:
    """Load settings with precedence: defaults < user < workspace < env"""
    settings = {}
    
    # User settings
    user_path = Path.home() / ".henchman" / "settings.yaml"
    if user_path.exists():
        settings = deep_merge(settings, yaml.safe_load(user_path.read_text()))
    
    # Workspace settings
    workspace_path = Path.cwd() / ".henchman" / "settings.yaml"
    if workspace_path.exists():
        settings = deep_merge(settings, yaml.safe_load(workspace_path.read_text()))
    
    # Environment overrides
    if provider := os.environ.get("HENCHMAN_PROVIDER"):
        settings.setdefault("providers", {})["default"] = provider
    
    return Settings(**settings)
```

### Context Loading (HENCHMAN.md + GitHub Copilot Instructions)

Context files provide project-specific instructions to the agent. Multiple formats are supported:

| File | Location | Purpose |
|------|----------|--------|
| `HENCHMAN.md` | `~/.henchman/`, ancestors, subdirs | MLG-native context |
| `.github/copilot-instructions.md` | Workspace root | GitHub Copilot compatibility |

```python
# henchman/core/context.py

class ContextLoader:
    CONTEXT_FILES = [
        "HENCHMAN.md",
        ".github/copilot-instructions.md",
    ]
    
    def discover_files(self) -> list[Path]:
        """Find all context files in hierarchy"""
        files = []
        # Global: ~/.henchman/HENCHMAN.md
        # Workspace: .github/copilot-instructions.md
        # Ancestors: walk up to git root for HENCHMAN.md
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
- HENCHMAN.md files discovered and concatenated
- `.github/copilot-instructions.md` loaded when present

---

## Phase 7: Terminal UI ✅

**Goal**: Rich terminal interface with streaming output

**Status**: COMPLETE (2026-01-23)

### Tasks

- [x] **7.1** Set up Rich console and themes (Theme, ThemeManager, OutputRenderer)
- [x] **7.2** Implement input handling with prompt_toolkit (InputHandler)
- [x] **7.3** Implement streaming markdown output
- [x] **7.4** Implement tool confirmation dialogs (framework ready)
- [x] **7.5** Add status bar with context info
- [x] **7.6** Implement slash command parsing (Command, CommandRegistry, builtins)
- [x] **7.7** Implement at-command (@file) parsing
- [x] **7.8** Implement shell mode (!)
- [x] **7.9** Add unit tests (100% coverage, 363 tests)

### Main CLI Loop

```python
# henchman/cli/app.py

async def run_cli():
    console = Console()
    settings = load_settings()
    provider = create_provider(settings)
    tools = create_tool_registry(settings)
    agent = Agent(provider, tools, system_prompt=load_context())
    
    session = PromptSession(history=FileHistory(".henchman_history"))
    
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
# henchman/cli/commands/

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

## Phase 8: Session Management ✅

**Goal**: Save and restore conversation sessions

**Status**: Completed January 2026

### Tasks

- [x] **8.1** Define session data model
- [x] **8.2** Implement session persistence (JSON)
- [x] **8.3** Implement `/chat save <tag>`
- [x] **8.4** Implement `/chat resume <tag>`
- [x] **8.5** Implement `/chat list`
- [x] **8.6** Add auto-save on exit (deferred to main loop integration)

### Session Model

```python
# henchman/core/session.py

@dataclass
class SessionMessage:
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

@dataclass
class SessionMetadata:
    id: str
    tag: str | None
    project_hash: str
    started: str
    last_updated: str
    message_count: int

@dataclass
class Session:
    id: str
    project_hash: str
    started: str
    last_updated: str
    messages: list[SessionMessage]
    tag: str | None = None
    
class SessionManager:
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or (Path.home() / ".henchman" / "sessions")
    
    def create_session(self, project_hash: str, tag: str | None = None) -> Session: ...
    def save(self, session: Session) -> Path: ...
    def load(self, session_id: str) -> Session: ...
    def load_by_tag(self, tag: str, project_hash: str | None = None) -> Session | None: ...
    def list_sessions(self, project_hash: str | None = None) -> list[SessionMetadata]: ...
    def delete(self, session_id: str) -> None: ...
    def compute_project_hash(self, directory: Path) -> str: ...
```

### Acceptance Criteria

- ✅ Sessions save with all messages
- ✅ Sessions restore history correctly
- ✅ Project-scoped session listing
- ⏳ Auto-save on graceful exit (requires Phase 12 main loop)

---

## Phase 9: MCP Integration ✅

**Goal**: Support Model Context Protocol servers

**Status**: Completed January 2026

### Tasks

- [x] **9.1** Add `mcp` package dependency
- [x] **9.2** Implement `McpClient` for single server
- [x] **9.3** Implement `McpManager` for multiple servers
- [x] **9.4** Implement `McpTool` wrapper as internal Tool
- [x] **9.5** Add MCP server configuration (McpServerConfig)
- [x] **9.6** Implement `/mcp list` and `/mcp status` commands

### MCP Configuration

```yaml
# ~/.henchman/settings.yaml
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
# henchman/mcp/client.py

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

- ✅ Can connect to MCP servers
- ✅ Tools discovered and registered
- ✅ Tool execution works through MCP
- ✅ Trusted servers skip confirmation (use ToolKind.READ)

---

## Phase 10: Extensions & Plugins ✅

**Goal**: Allow third-party extensions

### Tasks

- [x] **10.1** Define `Extension` base class
- [x] **10.2** Implement entry point discovery
- [x] **10.3** Implement directory-based extensions
- [x] **10.4** Create extension loading system
- [x] **10.5** Implement `/extensions` command

### Extension Interface

```python
# henchman/extensions/base.py

class Extension(ABC):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def description(self) -> str: ...
    
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
[project.entry-points."henchman.extensions"]
my_extension = "my_package:MyExtension"

# Directory-based
~/.henchman/extensions/my-ext/extension.py
```

### ExtensionManager Usage

```python
from henchman.extensions import Extension, ExtensionManager
from pathlib import Path

# Create manager and discover extensions
manager = ExtensionManager()
manager.discover_entry_points()  # From installed packages
manager.discover_directory(Path.home() / ".henchman" / "extensions")

# Use discovered extensions
tools = manager.get_all_tools()
commands = manager.get_all_commands()
context = manager.get_combined_context()
```

### Acceptance Criteria

- ✅ Entry point extensions load
- ✅ Directory extensions load
- ✅ Extension tools register correctly
- ✅ Extension commands work

---

## Phase 11: Advanced Features (Partial)

**Goal**: Implement remaining gemini-cli features

### Tasks

- [ ] **11.1** Checkpointing (file state snapshots before edits) - DEFERRED
- [ ] **11.2** Sandboxing (Docker container execution) - DEFERRED
- [ ] **11.3** Hooks system (before/after events) - DEFERRED
- [x] **11.4** Headless mode (`--prompt` flag) - ✅ Implemented in Phase 12
- [x] **11.5** JSON output mode (`--output-format json`) - ✅ Implemented in Phase 12
- [x] **11.6** Multiple providers (Anthropic, Ollama) ✅

### Implemented: Multiple Providers

#### AnthropicProvider

Native Claude SDK integration with streaming support:

```python
from henchman.providers import AnthropicProvider

provider = AnthropicProvider(api_key="sk-ant-...", model="claude-sonnet-4-20250514")
async for chunk in provider.chat_completion_stream(messages):
    print(chunk.content, end="")
```

Supported models:
- claude-sonnet-4-20250514 (default)
- claude-3-7-sonnet-20250219
- claude-3-5-sonnet-20241022
- claude-3-5-haiku-20241022
- claude-3-opus-20240229

#### OllamaProvider

Local model support via Ollama's OpenAI-compatible API:

```python
from henchman.providers import OllamaProvider

provider = OllamaProvider(model="llama3.2")  # No API key needed
async for chunk in provider.chat_completion_stream(messages):
    print(chunk.content, end="")
```

### Headless Mode

```bash
# Simple prompt
henchman --prompt "Explain this code" < file.py

# JSON output for scripting
henchman -p "Summarize README.md" --output-format json

# Streaming JSON for real-time
henchman -p "Run tests" --output-format stream-json
```

### Hooks System

```python
# ~/.henchman/hooks/before_tool/validate.py
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

## Phase 13: Skills & Learning (Partial) ✅

**Goal**: Enable agent to learn and reuse successful task patterns

### Tasks

- [x] **13.1** Define `Skill` model and `SkillStep` types
- [x] **13.2** Implement `SkillStore` with git-backed storage
- [ ] **13.3** Implement `SkillLearner` for extracting skills from sessions
- [ ] **13.4** Implement `SkillExecutor` for replaying skills
- [ ] **13.5** Add skill detection heuristics to agent
- [ ] **13.6** Implement `/skill` commands (list, show, run, delete, etc.)
- [ ] **13.7** Support `.github/skills/` directory format
- [ ] **13.8** Add skill import/export and remote sync
- [x] Verification: Skills engine handles errors and replaying correctly (Models and Store verified)

### Skill Storage Formats

Skills can be stored in two formats:

| Format | Location | Use Case |
|--------|----------|----------|
| YAML | `~/.henchman/skills/*.skill.yaml` | User-learned skills |
| Markdown | `.github/skills/<name>/SKILL.md` | Shareable, repo-committed skills |

### YAML Format (User Skills)

```yaml
# ~/.henchman/skills/add-api-endpoint.skill.yaml
name: add-api-endpoint
description: Create a new REST API endpoint with router, handler, and tests
version: 1
created: 2026-01-23T10:30:00Z
author: matthew
tags: [api, fastapi, backend]

triggers:
  - "add a new endpoint"
  - "create an API route"

parameters:
  resource:
    description: "Name of the resource (e.g., users, products)"
    required: true

steps:
  - description: "Create router file"
    tool: write_file
    arguments:
      path: "src/api/routers/{{resource}}.py"
      content: |
        from fastapi import APIRouter
        router = APIRouter(prefix="/{{resource}}")
```

### Markdown Format (GitHub Skills)

```markdown
<!-- .github/skills/add-endpoint/SKILL.md -->
# add-endpoint

Create a new REST API endpoint with router and tests.

## Triggers

- "add a new endpoint"
- "create an API route for {resource}"

## Parameters

| Name | Required | Description |
|------|----------|-------------|
| resource | yes | Name of the resource |
| methods | no | HTTP methods (default: GET, POST) |

## Steps

### 1. Create router file

**Tool:** `write_file`

```python
# Path: src/api/routers/{{resource}}.py
from fastapi import APIRouter

router = APIRouter(prefix="/{{resource}}", tags=["{{resource}}"])

@router.get("/")
async def list_{{resource}}():
    return []
```

### 2. Register router

**Tool:** `edit_file`

Add import and include router in `src/api/main.py`.
```

### Git-Backed Storage

```python
# henchman/skills/storage.py

class SkillStore:
    def __init__(self, path: Path = None):
        self.path = path or Path.home() / ".henchman" / "skills"
        self._ensure_git_repo()
    
    def _ensure_git_repo(self) -> None:
        """Initialize git repo for version history"""
        if not (self.path / ".git").exists():
            subprocess.run(["git", "init"], cwd=self.path)
    
    def save(self, skill: Skill, message: str = None) -> None:
        """Save skill and commit to git"""
        ...
    
    def history(self, skill_name: str) -> list[SkillVersion]:
        """Get version history from git log"""
        ...
    
    def rollback(self, skill_name: str, commit: str) -> None:
        """Restore skill to previous version"""
        ...
```

### Agent Behavior

**Learning** (agent-initiated):
```
✅ Done! I created the products endpoint.

💡 This looks like a reusable pattern. Should I remember this as a skill?
   [Yes, save skill] [No thanks]
```

**Usage** (agent-driven with announcement):
```
❯ I need an orders endpoint

🎯 Using learned skill: add-api-endpoint
   Parameters: resource=orders
```

### Slash Commands

```
/skill list                    # List all skills
/skill show <name>             # Show skill steps
/skill run <name> [--param=val]  # Execute skill
/skill history <name>          # Version history (git log)
/skill rollback <name> <hash>  # Restore version
/skill edit <name>             # Open in $EDITOR
/skill delete <name>           # Remove skill
/skill export <name>           # Print to stdout
/skill import <path|url>       # Import from file/URL
/skill remote [add|push|pull]  # Git remote sync
```

### Acceptance Criteria

- Skills save in YAML format with git commits
- `.github/skills/*/SKILL.md` files discovered and loaded
- Agent offers to save skill-worthy completions
- Agent announces when using learned skills
- Skills shareable via export/import or git remotes
- Verification: Skills engine handles errors and replaying correctly

---

## Phase 14: Enhanced Interaction & Context ✅

**Goal**: Improve user control, safety, and context awareness

**Status**: COMPLETE (2026-01-23)

### Tasks

- [x] **14.1** **Escape Key Support**
    - [x] 14.1.1 Bind `Keys.Escape` in `InputHandler` (prompt_toolkit) to cancel signal
    - [x] 14.1.2 Implement async cancellation in `Agent.run` loop
    - [x] 14.1.3 Ensure `Tool.execute` respects cancellation (timeouts/interrupts)
    - [x] 14.1.4 UX: Visual feedback for cancelled operations

- [x] **14.2** **Plan Mode** (`/plan`)
    - [x] 14.2.1 Implement `/plan` toggle command
    - [x] 14.2.2 Create `PlanMode` state in Session
    - [x] 14.2.3 Enforce "Read-Only" policy in `PolicyEngine` when in Plan Mode
    - [x] 14.2.4 Allow writing to temporary/scratchpad areas only
    - [x] 14.2.5 System Prompt injection: "You are in PLAN MODE..."
    - [x] 14.2.6 UX: Yellow/Distinct theme or status indicator for Plan Mode

- [x] **14.3** **Context Intelligence**
    - [x] 14.3.1 Implement `TokenCounter` utility
    - [x] 14.3.2 Display "Tokens: Used/Max" in Status Bar
    - [x] 14.3.3 Implement `ContextCompactor` (Summary/Pruning strategies)
    - [x] 14.3.4 Add configuration for auto-compaction thresholds

---

## Phase 15: Reinforced Memory System

**Goal**: Enable agent to build persistent, weighted memory that strengthens through use

### Overview

Memory uses a reinforcement model where facts gain strength when used successfully and decay when unused, mimicking human memory patterns.

### Tasks

- [ ] **15.1** Define `Fact` model with weight, uses, decay_rate
- [ ] **15.2** Implement `ReinforcedMemory` store with YAML persistence
- [ ] **15.3** Implement reinforcement logic (strengthen on success, weaken on failure)
- [ ] **15.4** Implement Ebbinghaus decay curve for unused memories
- [ ] **15.5** Add `remember` tool for agent to store facts
- [ ] **15.6** Add `memory_feedback` tool for explicit reinforcement
- [ ] **15.7** Integrate memory into system prompt via `ContextLoader`
- [ ] **15.8** Implement `/memory` commands (show, add, forget, prune)
- [ ] **15.9** Add memory visualization in REPL status

### Memory Model

```python
# henchman/core/memory.py

@dataclass
class Fact:
    id: str
    content: str
    weight: float = 1.0          # Strength (0-10)
    uses: int = 0                # Times recalled
    created: datetime
    last_used: datetime
    decay_rate: float = 0.1      # Daily decay when unused
    scope: Literal["project", "user"] = "project"
    
    def reinforce(self, success: bool = True) -> None:
        """Strengthen or weaken based on outcome"""
        self.uses += 1
        self.last_used = datetime.now()
        
        if success:
            # Diminishing returns: harder to strengthen strong memories
            boost = 1.0 / (1 + self.weight * 0.1)
            self.weight = min(10.0, self.weight + boost)
        else:
            self.weight = max(0.0, self.weight - 0.5)
    
    def apply_decay(self) -> None:
        """Ebbinghaus forgetting curve - strong memories decay slower"""
        days_unused = (datetime.now() - self.last_used).days
        if days_unused > 0:
            decay = self.decay_rate * (1 / (1 + self.weight * 0.1))
            self.weight = max(0.0, self.weight - (decay * days_unused))
```

### Memory Storage

```yaml
# .henchman/memory.yaml (project) or ~/.henchman/memory.yaml (user)
facts:
  - id: f_001
    content: "API routes go in src/api/routers/"
    weight: 8.5
    uses: 12
    created: 2026-01-15T10:30:00Z
    last_used: 2026-01-23T14:22:00Z
    decay_rate: 0.1
    
  - id: f_002
    content: "User prefers pytest over unittest"
    weight: 2.3
    uses: 2
    created: 2026-01-20T09:00:00Z
    last_used: 2026-01-21T11:00:00Z
    decay_rate: 0.1
```

### ReinforcedMemory Manager

```python
class ReinforcedMemory:
    def __init__(self, project_path: Path, user_path: Path):
        self.project_path = project_path / ".henchman" / "memory.yaml"
        self.user_path = user_path / ".henchman" / "memory.yaml"
        self.recall_threshold = 1.0  # Minimum weight to include
    
    def recall(self, limit: int = 20) -> list[Fact]:
        """Get facts above threshold, sorted by weight"""
        self.apply_all_decay()
        active = [f for f in self.facts if f.weight >= self.recall_threshold]
        active.sort(key=lambda f: f.weight, reverse=True)
        return active[:limit]
    
    def remember(self, content: str, scope: str = "project") -> Fact:
        """Add new fact or reinforce existing similar fact"""
        existing = self._find_similar(content)
        if existing:
            existing.reinforce(success=True)
            return existing
        return self._create_fact(content, scope)
    
    def feedback(self, fact_id: str, helpful: bool) -> None:
        """Explicit feedback strengthens or weakens fact"""
        fact = self._get_by_id(fact_id)
        if fact:
            fact.reinforce(success=helpful)
    
    def to_context(self) -> str:
        """Format strong memories for system prompt"""
        facts = self.recall(limit=15)
        if not facts:
            return ""
        
        lines = ["## What I Remember"]
        for f in facts:
            strength = "●" * int(f.weight) + "○" * (10 - int(f.weight))
            lines.append(f"- [{strength}] {f.content}")
        return "\n".join(lines)
```

### Reinforcement Triggers

| Trigger | Weight Change |
|---------|---------------|
| Fact used, task succeeded | +0.5 to +1.0 (diminishing returns) |
| Fact used, task failed | -0.5 |
| User says "that's wrong" | -1.0 |
| User confirms fact | +1.0 |
| Day passes unused | -decay_rate × (weaker decay for strong facts) |
| Weight drops below 0.5 | Excluded from context |
| Weight drops below 0.1 | Archived/pruned |

### Tools

```python
class RememberTool(Tool):
    name = "remember"
    description = "Store a fact for future reference"
    kind = ToolKind.WRITE
    
    parameters = {
        "type": "object",
        "properties": {
            "fact": {"type": "string"},
            "scope": {"enum": ["project", "user"], "default": "project"},
        },
        "required": ["fact"]
    }

class MemoryFeedbackTool(Tool):
    name = "memory_feedback"
    description = "Mark a remembered fact as helpful or not"
    kind = ToolKind.READ
    
    parameters = {
        "type": "object",
        "properties": {
            "fact_id": {"type": "string"},
            "helpful": {"type": "boolean"},
        },
        "required": ["fact_id", "helpful"]
    }
```

### Slash Commands

```
/memory                     # Show all memories with strength visualization
/memory add <fact>          # Manually add a fact
/memory forget <id>         # Remove a specific fact
/memory prune               # Remove all weak memories (weight < 1.0)
/memory export              # Export memories to YAML
/memory import <path>       # Import memories from file
```

### REPL Visualization

```
❯ /memory

📚 Memory (15 facts, 3 forgotten)

Strong (weight 7+):
  ●●●●●●●●○○ "API routes go in src/api/routers/" (12 uses)
  ●●●●●●●○○○ "Run ./scripts/ci.sh before commits" (8 uses)

Medium (weight 3-7):
  ●●●●○○○○○○ "User prefers detailed explanations" (4 uses)

Weak (weight 1-3):
  ●●○○○○○○○○ "Database migrations in alembic/" (1 use, decaying)

💀 Forgotten (weight < 1): 3 facts pruned
```

### Acceptance Criteria

- Facts persist in YAML at project and user level
- Weight increases on successful use (diminishing returns)
- Weight decreases on failure or explicit negative feedback
- Unused facts decay over time (Ebbinghaus curve)
- Only facts above threshold appear in context
- Agent can use `remember` tool to store new facts
- `/memory` commands work for manual management

---

## Phase 12: Polish & Release

**Goal**: Production-ready release

### Tasks

- [x] **12.1** Interactive REPL main loop (wire Agent + InputHandler + OutputRenderer)
- [x] **12.2** Headless mode with `--prompt` argument
- [x] **12.3** Session auto-save on graceful exit
- [x] **12.4** Comprehensive test suite (>80% coverage) - Achieved 100%!
- [x] **12.5** Documentation site (mkdocs)
- [x] **12.6** Rebrand to henchman-ai (completed)
- [x] **12.7** PyPI packaging and publishing
- [x] **12.8** GitHub Actions CI/CD
- [x] **12.9** Multiple theme support (in console.py)
- [ ] **12.10** Performance optimization (optional)
- [ ] **12.11** Error handling audit (optional)
- [ ] **12.12** Security review (optional)

### 12.6 Rename Checklist: henchman → henchman

Before PyPI publishing, rename the package from `henchman` to `henchman`:

| Item | From | To |
|------|------|-----|
| Package directory | `src/henchman/` | `src/henchman/` |
| CLI entry point | `henchman` | `henchman` |
| PyPI package name | `henchman-ai` | `henchman-ai` |
| Config directories | `~/.henchman/`, `.henchman/` | `~/.henchman/`, `.henchman/` |
| Context files | `HENCHMAN.md` | `HENCHMAN.md` (keep `.github/copilot-instructions.md`) |
| Environment prefix | `HENCHMAN_*` | `HENCHMAN_*` |
| Shell detection var | `HENCHMAN_CLI=1` | `HENCHMAN_CLI=1` |
| Error base class | `MlgError` | `HenchmanError` |
| Repository name | `henchman-ai` | `henchman` |

**Scrub script** (run before final commit):
```bash
# Rename directories
mv src/henchman src/henchman

# Update all imports and references
find src tests -name "*.py" -exec sed -i 's/from henchman/from henchman/g' {} +
find src tests -name "*.py" -exec sed -i 's/import henchman/import henchman/g' {} +
find . -name "*.md" -exec sed -i 's/henchman-ai/henchman/g' {} +
find . -name "*.md" -exec sed -i 's/MLG/HENCHMAN/g' {} +

# Update pyproject.toml
sed -i 's/name = "henchman-ai"/name = "henchman"/' pyproject.toml
sed -i 's/henchman = "henchman.cli.app:main"/henchman = "henchman.cli.app:main"/' pyproject.toml

# Verify no henchman references remain
grep -r "henchman" src/ tests/ --include="*.py" | grep -v henchman
```

### Completed (12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9)

**12.1 Interactive REPL Main Loop**

Created `src/henchman/cli/repl.py` with:
- `ReplConfig` dataclass for REPL configuration
- `Repl` class orchestrating Agent, ToolRegistry, CommandRegistry, OutputRenderer
- Event-driven processing of agent responses (content, thinking, tool calls, errors)
- Slash command handling (/quit, /clear, /help, /tools)
- Tool execution with confirmation flow
- Graceful handling of Ctrl+C and Ctrl+D

**12.2 Headless Mode**

Updated `src/henchman/cli/app.py` with:
- `_get_provider()` - Provider initialization from env or settings
- `_run_interactive()` - Launches REPL for interactive mode
- `_run_headless()` - Processes single prompt and exits
- `--prompt/-p` CLI option for headless execution
- Support for text, json, and stream-json output formats

**12.3 Session Auto-Save**

Updated `src/henchman/cli/repl.py` with:
- `session_manager` and `session` fields on Repl
- `_auto_save_session()` method in finally block
- Records user and assistant messages during conversation

**12.9 JSON Output Mode**

Created `src/henchman/cli/json_output.py` with:
- `JsonOutputRenderer` class for JSON formatting
- Support for `--output-format json` (single JSON object per event)
- Support for `--output-format stream-json` (one JSON object per line)
- Proper handling of all event types with enum to string conversion
- Skips saving empty sessions
- 5 new tests for auto-save functionality

**12.4 Test Coverage**

- 567+ tests passing
- 100% line and branch coverage
- All linting (ruff) and type checking (mypy) passing

**12.5 Documentation Site**

Created mkdocs documentation with Material theme:
- `docs/index.md` - Overview and features
- `docs/getting-started.md` - Installation and usage
- `docs/configuration.md` - Settings reference
- `docs/providers.md` - LLM provider setup
- `docs/tools.md` - Built-in tools reference
- `docs/mcp.md` - MCP integration guide
- `docs/extensions.md` - Extension development
- `docs/api.md` - API reference

**12.6 Rebrand to henchman-ai**

Completed full rebrand:
- Package: `src/mlg` → `src/henchman`
- CLI: `mlg` → `henchman`
- Env vars: `MLG_*` → `HENCHMAN_*`
- Config: `~/.mlg` → `~/.henchman`
- Context: `MLG.md` → `HENCHMAN.md`

**12.7 PyPI Packaging**

- Updated pyproject.toml with classifiers
- Added CHANGELOG.md
- Python 3.10+ support

**12.8 GitHub Actions CI/CD**

Created workflows:
- `.github/workflows/ci.yml` - lint, type-check, test, build
- `.github/workflows/publish.yml` - PyPI publishing on release
- `.github/workflows/docs.yml` - GitHub Pages deployment

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
| **Context Filename** | HENCHMAN.md vs AGENT.md | HENCHMAN.md (matches project) |
| **Default Provider** | DeepSeek vs Ollama | DeepSeek (easy API, free tier) |

---

*Document Version: 1.0*  
*Last Updated: January 23, 2026*
