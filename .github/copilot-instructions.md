# MLG-CLI Copilot Instructions

MLG-CLI is a **model-agnostic AI agent CLI** in Python, inspired by gemini-cli. It supports multiple LLM providers (DeepSeek, OpenAI, Anthropic, Ollama) via a unified provider abstraction.

## Project Status

- **Phase 1**: Project Foundation ✅
- **Phase 2**: Provider System ✅
- **Phase 3**: Core Agent Loop ✅
- **Phase 4**: Tool System ✅
- **Phases 5-12**: See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)

## Architecture Overview

```
src/mlg/
├── cli/        # UI layer: Rich console, prompt_toolkit input, slash commands
├── core/       # Agent layer: AgentLoop, EventBus, ToolRegistry, PolicyEngine
├── providers/  # Model providers: OpenAICompatible base, DeepSeek, Anthropic, Ollama
├── tools/      # Built-in tools: read_file, write_file, shell, grep, glob, web_fetch
├── mcp/        # MCP integration: McpClient, McpManager, McpTool wrapper
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
from mlg.providers import DeepSeekProvider, Message

# Create provider
provider = DeepSeekProvider(api_key="your-key")

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
    if event.event_type == EventType.CONTENT:
        print(event.data, end="")
    elif event.event_type == EventType.TOOL_CALL_REQUEST:
        # Handle tool call
        tool_call = event.data
        result = execute_tool(tool_call)
        agent.submit_tool_result(tool_call.id, result)
    elif event.event_type == EventType.FINISHED:
        break

# Continue after tool results
async for event in agent.continue_with_tool_results():
    ...
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

### Configuration Hierarchy (Planned)
Settings merge: defaults < `~/.mlg/settings.yaml` < `.mlg/settings.yaml` < env vars. Use `MLG_PROVIDER` to override default provider.

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
│   ├── cli/app.py              # CLI application (click)
│   └── providers/              # Provider implementations
│       ├── base.py             # Message, ToolCall, StreamChunk, ModelProvider
│       ├── openai_compat.py    # OpenAICompatibleProvider
│       ├── deepseek.py         # DeepSeekProvider
│       └── registry.py         # ProviderRegistry
├── tests/                      # Test suite (mirrors src structure)
├── scripts/ci.sh               # CI pipeline script
├── pyproject.toml              # Project configuration
└── IMPLEMENTATION_PLAN.md      # 12-phase roadmap
```

## Implementation Reference

See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) for the 12-phase implementation roadmap with detailed code examples for each component.
