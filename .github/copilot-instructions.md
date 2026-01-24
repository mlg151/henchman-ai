# MLG-CLI Copilot Instructions

MLG-CLI is a **model-agnostic AI agent CLI** in Python, inspired by gemini-cli. It supports multiple LLM providers (DeepSeek, OpenAI, Anthropic, Ollama) via a unified provider abstraction.

## Project Status

- **Phase 1**: Project Foundation ✅
- **Phase 2**: Provider System ✅
- **Phase 3**: Core Agent Loop ✅
- **Phase 4**: Tool System ✅
- **Phase 5**: Built-in Tools ✅
- **Phase 6**: Configuration System ✅
- **Phase 7**: Terminal UI ✅
- **Phase 8**: Session Management ✅
- **Phase 9**: MCP Integration ✅
- **Phase 10**: Extensions & Plugins ✅
- **Phase 11**: Advanced Features (Multiple Providers ✅, others deferred)
- **Phase 12**: Polish & Release - See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)

## Architecture Overview

```
src/mlg/
├── cli/        # UI layer: Rich console, prompt_toolkit input, slash commands
├── core/       # Agent layer: AgentLoop, EventBus, ToolRegistry, PolicyEngine
├── providers/  # Model providers: OpenAICompatible base, DeepSeek, Anthropic, Ollama
├── tools/      # Built-in tools: read_file, write_file, shell, grep, glob, web_fetch
├── mcp/        # MCP integration: McpClient, McpManager, McpTool wrapper
├── extensions/ # Plugin system: Extension ABC, ExtensionManager, /extensions command
├── config/     # Pydantic settings, hierarchical YAML loading, MLG.md context
└── utils/      # Utility functions and helpers
```

**Key insight**: DeepSeek uses OpenAI-compatible API, so `OpenAICompatibleProvider` handles DeepSeek, OpenAI, Together, Groq, and similar APIs.

## Development Setup

```bash
pip install -e ".[dev]"       # Install in editable mode with dev deps
./scripts/ci.sh               # Run full CI pipeline
mlg --version                 # Verify CLI entry point
```

## CI Pipeline

Run `./scripts/ci.sh` to execute:
1. **Ruff** - Linting
2. **Mypy** - Type checking  
3. **Pytest** - Tests with 100% coverage requirement
4. **Doctests** - Documentation examples
5. **Doc coverage** - All public functions must have docstrings

## Quality Requirements

- **100% test coverage** - All code must be tested
- **100% documentation coverage** - All public functions/classes need docstrings
- **Type hints** - All function signatures must have type hints
- **Linting** - Must pass ruff and mypy

## Key Patterns

### Provider System (Implemented)

```python
from mlg.providers import DeepSeekProvider, AnthropicProvider, OllamaProvider, Message

# DeepSeek (default)
provider = DeepSeekProvider(api_key="your-key")

# Anthropic Claude
provider = AnthropicProvider(api_key="sk-ant-...", model="claude-sonnet-4-20250514")

# Ollama (local, no API key)
provider = OllamaProvider(model="llama3.2")

# Stream chat completion
async for chunk in provider.chat_completion_stream(
    messages=[Message(role="user", content="Hello")],
    tools=[...],  # Optional tool declarations
):
    if chunk.content:
        print(chunk.content, end="")
    if chunk.finish_reason:
        break
```

### Available Providers

| Provider | API Key Env Var | Default Model | Notes |
|----------|----------------|---------------|-------|
| `deepseek` | `DEEPSEEK_API_KEY` | deepseek-chat | OpenAI-compatible |
| `anthropic` | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 | Native SDK |
| `ollama` | None required | llama3.2 | Local models |

### Core Types

```python
from mlg.providers import (
    Message,           # Conversation message (role, content, tool_calls)
    ToolCall,          # Tool invocation request (id, name, arguments)
    ToolDeclaration,   # Tool schema for LLM (name, description, parameters)
    StreamChunk,       # Streaming response (content, tool_calls, finish_reason)
    FinishReason,      # STOP, TOOL_CALLS, LENGTH, CONTENT_FILTER
)
```

### Provider Registry

```python
from mlg.providers import get_default_registry

registry = get_default_registry()
provider = registry.create("deepseek", api_key="...", model="deepseek-chat")
```

### Async Generators for Streaming
All LLM interactions stream via async generators. Use `AsyncIterator[StreamChunk]` for provider responses:
```python
async for chunk in provider.chat_completion_stream(messages, tools=...):
    yield AgentEvent(EventType.CONTENT, chunk.content)
```

### Core Agent Loop

The Agent class orchestrates LLM interactions with event streaming:

```python
from mlg.core import Agent, AgentEvent, EventType
from mlg.providers import DeepSeekProvider

# Create provider and agent
provider = DeepSeekProvider(api_key="...", model="deepseek-chat")
agent = Agent(provider=provider, system_prompt="You are a helpful assistant.")

# Stream agent events
async for event in agent.run("Hello, world!"):
    if event.type == EventType.CONTENT:
        print(event.data, end="")
    elif event.type == EventType.TOOL_CALL_REQUEST:
        # Handle tool call
        tool_call = event.data
        result = execute_tool(tool_call)
        agent.submit_tool_result(tool_call.id, result)
    elif event.type == EventType.FINISHED:
        break

# Continue after tool results
async for event in agent.continue_with_tool_results():
    ...
```

### Interactive REPL (Implemented)

The Repl class provides the main interactive loop:

```python
from mlg.cli import Repl, ReplConfig
from mlg.providers import DeepSeekProvider

# Create provider and REPL
provider = DeepSeekProvider(api_key="...")
config = ReplConfig(system_prompt="You are helpful", auto_save=True)
repl = Repl(provider=provider, config=config)

# Run interactive mode
import anyio
anyio.run(repl.run)
```

**REPL Features:**
- Slash commands (/quit, /clear, /help, /tools)
- @file reference expansion
- !shell command execution
- Tool call execution with confirmation
- Streaming output with Rich console

**CLI Usage:**
```bash
# Interactive mode
mlg

# Headless mode (single prompt)
mlg --prompt "What is 2+2?"
mlg -p "Summarize this file: @document.txt"
```

**Event Types:**
- `CONTENT` - Text content from LLM
- `THOUGHT` - Thinking/reasoning content (for models that support it)
- `TOOL_CALL_REQUEST` - LLM requests a tool call
- `TOOL_CALL_RESULT` - Result of a tool call
- `TOOL_CONFIRMATION` - User confirmation for tool execution
- `ERROR` - Error occurred
- `FINISHED` - Stream complete

### Tool System

Tools extend the `Tool` ABC with a `ToolKind` that determines auto-approval:
- `ToolKind.READ` → auto-approved (read_file, ls, glob)
- `ToolKind.WRITE`/`EXECUTE`/`NETWORK` → require confirmation

```python
from mlg.tools import Tool, ToolKind, ToolResult, ToolRegistry, ConfirmationRequest

# Define a custom tool
class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Does something useful"
    
    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        }
    
    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ  # Auto-approved
    
    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content=f"Result: {params.get('input')}")

# Register and use tools
registry = ToolRegistry()
registry.register(MyTool())

# Get declarations for LLM
declarations = registry.get_declarations()

# Execute a tool
result = await registry.execute("my_tool", {"input": "hello"})

# Set confirmation handler for non-read tools
async def confirm(request: ConfirmationRequest) -> bool:
    return True  # Auto-approve in this example

registry.set_confirmation_handler(confirm)

# Auto-approve specific tools (bypass confirmation)
registry.add_auto_approve_policy("write_file")
```

### Configuration System (Implemented)

Settings are loaded hierarchically with later sources overriding earlier ones:

```python
from mlg.config import load_settings, Settings, ContextLoader

# Load settings (automatically discovers and merges files)
settings = load_settings()

# Access provider settings
print(settings.providers.default)  # "deepseek"
print(settings.providers.deepseek)  # {"model": "deepseek-chat"}

# Access tool settings
print(settings.tools.shell_timeout)  # 60
print(settings.tools.auto_approve_read)  # True

# Load context files (MLG.md)
loader = ContextLoader()
context = loader.load()  # Concatenated content from all MLG.md files
```

**Settings Precedence** (later overrides earlier):
1. Defaults (Pydantic model defaults)
2. User settings (`~/.mlg/settings.yaml`)
3. Workspace settings (`.mlg/settings.yaml`)
4. Environment variables (`MLG_PROVIDER`, `MLG_MODEL`)

**Context File Discovery** (MLG.md):
- Global: `~/.mlg/MLG.md`
- Ancestors: Walk up from cwd to git root
- Subdirectories: Optional, respects `.gitignore`

### Terminal UI (Implemented)

The CLI provides a Rich-based terminal interface with theming and commands:

```python
from mlg.cli import OutputRenderer, Theme, ThemeManager
from mlg.cli.commands import CommandRegistry, parse_command
from mlg.cli.commands.builtins import get_builtin_commands

# Create themed output renderer
renderer = OutputRenderer()
renderer.success("Operation completed")
renderer.warning("Be careful")
renderer.error("Something went wrong")
renderer.markdown("# Heading\n\nSome **bold** text")

# Parse slash commands
result = parse_command("/help")  # ("help", [])
result = parse_command("/model gpt-4")  # ("model", ["gpt-4"])

# Register and execute commands
registry = CommandRegistry()
for cmd in get_builtin_commands():
    registry.register(cmd)

# Check input types
from mlg.cli import is_slash_command, is_shell_command, expand_at_references

is_slash_command("/help")  # True
is_shell_command("!ls")    # True
await expand_at_references("Check @file.txt")  # Expands file content
```

**Built-in Commands:**
- `/help` - Show available commands
- `/quit` - Exit the CLI
- `/clear` - Clear the screen
- `/tools` - List available tools
- `/chat save [tag]` - Save current session
- `/chat list` - List saved sessions
- `/chat resume <tag>` - Resume a saved session

### Session Management (Implemented)

Sessions persist conversation history for later resumption:

```python
from mlg.core import Session, SessionManager, SessionMessage, SessionMetadata

# Create a session manager
manager = SessionManager()  # Uses ~/.mlg/sessions by default

# Create a new session for a project
project_hash = manager.compute_project_hash(Path.cwd())
session = manager.create_session(project_hash=project_hash, tag="my-feature")

# Add messages to session
session.messages.append(SessionMessage(role="user", content="Hello"))
session.messages.append(SessionMessage(role="assistant", content="Hi there!"))

# Save session to disk
manager.save(session)

# List sessions for current project
for meta in manager.list_sessions(project_hash):
    print(f"{meta.tag}: {meta.message_count} messages")

# Load session by tag
loaded = manager.load_by_tag("my-feature", project_hash)

# Delete a session
manager.delete(session.id)
```

**Session Data Model:**
- `SessionMessage` - A message with role, content, optional tool_calls/tool_call_id
- `Session` - Full session with id, project_hash, timestamps, messages, optional tag
- `SessionMetadata` - Lightweight summary without messages (for listing)
- `SessionManager` - CRUD operations, current session tracking, project hash computation

**Session Storage:**
- Sessions stored as JSON in `~/.mlg/sessions/`
- Each session is `{session_id}.json`
- Scoped by project_hash to isolate per-project

### MCP Integration (Implemented)

MCP (Model Context Protocol) enables connecting to external tool servers:

```python
from mlg.mcp import McpServerConfig, McpClient, McpManager, McpTool

# Configure an MCP server
config = McpServerConfig(
    command="npx",
    args=["@anthropic-ai/mcp-filesystem-server", "/home/user"],
    trusted=False,  # Untrusted servers require tool confirmation
)

# Connect to a single server
client = McpClient(name="filesystem", config=config)
await client.connect()
tools = await client.discover_tools()
result = await client.call_tool("read_file", {"path": "/etc/hosts"})
await client.disconnect()

# Or manage multiple servers
configs = {"filesystem": config, "github": github_config}
manager = McpManager(configs)
await manager.connect_all()
all_tools = manager.get_all_tools()  # List[McpTool]
await manager.disconnect_all()
```

**MCP Configuration (settings.yaml):**
```yaml
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

**MCP Commands:**
- `/mcp list` - List configured MCP servers and connection status
- `/mcp status` - Show connection status and available tools

**Key Types:**
- `McpServerConfig` - Server configuration (command, args, env, trusted)
- `McpClient` - Single server connection manager
- `McpManager` - Multi-server connection manager
- `McpTool` - Wraps MCP tools as internal Tool instances
- `McpToolResult` - Result from MCP tool execution

### Extensions System (Implemented)

Extensions allow third-party plugins to add tools, commands, and context:

```python
from mlg.extensions import Extension, ExtensionManager
from mlg.tools.base import Tool
from mlg.cli.commands import Command

# Define a custom extension
class MyExtension(Extension):
    @property
    def name(self) -> str:
        return "my_extension"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "My custom extension"

    def get_tools(self) -> list[Tool]:
        return [MyCustomTool()]

    def get_commands(self) -> list[Command]:
        return [MyCustomCommand()]

    def get_context(self) -> str:
        return "Additional system prompt context"

# Load extensions
manager = ExtensionManager()
manager.discover_entry_points()  # From installed packages
manager.discover_directory(Path.home() / ".mlg" / "extensions")
```

**Extension Discovery:**
- Entry points: Register in `pyproject.toml` under `[project.entry-points."mlg.extensions"]`
- Directory: Place `extension.py` with Extension subclass in `~/.mlg/extensions/<name>/`

**Built-in Commands:**
- `/extensions` - List loaded extensions with name, version, and description

## Conventions

- **Pydantic v2** for all data models and settings schemas
- **anyio** for async (not raw asyncio) to support multiple backends
- **Rich** for console output, **prompt_toolkit** for input
- **Click** for CLI framework
- Shell tool sets `MLG_CLI=1` env var for script detection
- Context files named `MLG.md` (discovered up directory tree)
- Custom exceptions inherit from `MlgError` base class
- Google-style docstrings for all public functions

## Testing

```python
# Mock providers for unit tests
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_provider():
    provider = AsyncMock(spec=ModelProvider)
    async def mock_stream(*args, **kwargs):
        yield StreamChunk(content="Hello")
    provider.chat_completion_stream = mock_stream
    return provider

# Mark integration tests that call real APIs
@pytest.mark.integration
async def test_real_api(): ...
```

## File Structure

```
mlg-cli/
├── src/mlg/                    # Main package
│   ├── __init__.py             # Package init, exports __version__
│   ├── __main__.py             # Entry point for python -m mlg
│   ├── version.py              # Version info (0.1.0)
│   ├── cli/                    # CLI and UI layer
│   │   ├── app.py              # CLI application (click)
│   │   ├── console.py          # OutputRenderer, Theme, ThemeManager
│   │   ├── input.py            # InputHandler, @file expansion, !shell
│   │   └── commands/           # Slash command system
│   │       ├── __init__.py     # Command, CommandRegistry, parse_command
│   │       ├── builtins.py     # HelpCommand, QuitCommand, ClearCommand, ToolsCommand
│   │       ├── chat.py         # ChatCommand for session management
│   │       ├── mcp.py          # McpCommand for MCP server management
│   │       └── extensions.py   # ExtensionsCommand for extension listing
│   ├── core/                   # Core agent system
│   │   ├── events.py           # EventType, AgentEvent
│   │   ├── agent.py            # Agent class
│   │   └── session.py          # Session, SessionMessage, SessionMetadata, SessionManager
│   ├── config/                 # Configuration system
│   │   ├── schema.py           # Settings, ProviderSettings, ToolSettings, UISettings
│   │   ├── settings.py         # load_settings, discover_settings_files, deep_merge
│   │   └── context.py          # ContextLoader for MLG.md files
│   ├── extensions/             # Extension/plugin system
│   │   ├── base.py             # Extension ABC
│   │   └── manager.py          # ExtensionManager, discovery
│   ├── mcp/                    # MCP (Model Context Protocol) integration
│   │   ├── config.py           # McpServerConfig
│   │   ├── client.py           # McpClient, McpToolResult, McpToolDefinition
│   │   ├── manager.py          # McpManager
│   │   └── tool.py             # McpTool wrapper
│   ├── providers/              # Provider implementations
│   │   ├── base.py             # Message, ToolCall, StreamChunk, ModelProvider
│   │   ├── openai_compat.py    # OpenAICompatibleProvider
│   │   ├── deepseek.py         # DeepSeekProvider
│   │   ├── anthropic.py        # AnthropicProvider (native Claude SDK)
│   │   ├── ollama.py           # OllamaProvider (local models)
│   │   └── registry.py         # ProviderRegistry
│   └── tools/                  # Tool system
│       ├── base.py             # Tool ABC, ToolKind, ToolResult
│       ├── registry.py         # ToolRegistry
│       └── builtins/           # Built-in tools
│           ├── file_read.py    # ReadFileTool
│           ├── file_write.py   # WriteFileTool
│           ├── file_edit.py    # EditFileTool
│           ├── ls.py           # LsTool
│           ├── glob_tool.py    # GlobTool
│           ├── grep.py         # GrepTool
│           ├── shell.py        # ShellTool
│           └── web_fetch.py    # WebFetchTool
├── tests/                      # Test suite (mirrors src structure)
├── scripts/ci.sh               # CI pipeline script
├── pyproject.toml              # Project configuration
└── IMPLEMENTATION_PLAN.md      # 12-phase roadmap
```

## Development Workflow

This project follows **Test-Driven Development (TDD)** with strict quality requirements:

### Standard Development Cycle

1. **Write tests first** - Create test cases for the feature before implementation
2. **Implement the feature** - Write the minimum code to pass tests
3. **Run CI checks** - Execute `./scripts/ci.sh` to verify:
   - Ruff linting passes
   - Mypy type checking passes
   - All tests pass with 100% coverage
   - Doctests pass
   - All public APIs have docstrings
4. **Update documentation** - Update IMPLEMENTATION_PLAN.md and copilot-instructions.md
5. **Commit and push** - Commit with descriptive message, push to GitHub

### CI Pipeline (`scripts/ci.sh`)

```bash
./scripts/ci.sh  # Runs all checks in order:
# 1. ruff check src/ tests/        - Linting
# 2. mypy src/                      - Type checking
# 3. pytest --cov-fail-under=100   - Tests with 100% coverage
# 4. python -m doctest              - Doctests
# 5. Check all public APIs have docstrings
```

### Quality Requirements

- **100% test coverage** - All code paths must be tested
- **100% documentation coverage** - All public functions/classes have docstrings
- **All linting passes** - No ruff or mypy errors
- **Google-style docstrings** - Consistent documentation format

### Adding New Features

1. Create test file in `tests/` matching source structure
2. Write test cases covering all functionality
3. Implement feature in `src/mlg/`
4. Add exports to `__init__.py` files
5. Run `./scripts/ci.sh` until all checks pass
6. Update relevant documentation

## Implementation Reference

See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) for the 12-phase implementation roadmap with detailed code examples for each component.
