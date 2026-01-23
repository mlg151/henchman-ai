# MLG-CLI Copilot Instructions

MLG-CLI is a **model-agnostic AI agent CLI** in Python, inspired by gemini-cli. It supports multiple LLM providers (DeepSeek, OpenAI, Anthropic, Ollama) via a unified provider abstraction.

## Architecture Overview

```
src/mlg/
├── cli/        # UI layer: Rich console, prompt_toolkit input, slash commands
├── core/       # Agent layer: AgentLoop, EventBus, ToolRegistry, PolicyEngine
├── providers/  # Model providers: OpenAICompatible base, DeepSeek, Anthropic, Ollama
├── tools/      # Built-in tools: read_file, write_file, shell, grep, glob, web_fetch
├── mcp/        # MCP integration: McpClient, McpManager, McpTool wrapper
└── config/     # Pydantic settings, hierarchical YAML loading, MLG.md context
```

**Key insight**: DeepSeek uses OpenAI-compatible API, so `OpenAICompatibleProvider` handles DeepSeek, OpenAI, Together, Groq, and similar APIs.

## Development Setup

```bash
pip install -e ".[dev]"       # Install in editable mode with dev deps
ruff check src/ tests/        # Linting
mypy src/                     # Type checking
pytest tests/ -v              # Run tests
mlg --version                 # Verify CLI entry point
```

## Key Patterns

### Async Generators for Streaming
All LLM interactions stream via async generators. Use `AsyncIterator[StreamChunk]` for provider responses and `AsyncIterator[AgentEvent]` for agent output:
```python
async for chunk in provider.chat_completion_stream(messages, tools=...):
    yield AgentEvent(EventType.CONTENT, chunk.content)
```

### Tool System with Confirmation Policies
Tools extend the `Tool` ABC with a `ToolKind` that determines auto-approval:
- `ToolKind.READ` → auto-approved (read_file, ls, glob)
- `ToolKind.WRITE`/`EXECUTE`/`NETWORK` → require confirmation

### Provider Abstraction
New providers implement `ModelProvider` protocol. For OpenAI-compatible APIs, extend `OpenAICompatibleProvider` and override `base_url`.

### Configuration Hierarchy
Settings merge: defaults < `~/.mlg/settings.yaml` < `.mlg/settings.yaml` < env vars. Use `MLG_PROVIDER` to override default provider.

## Conventions

- **Pydantic v2** for all data models and settings schemas
- **anyio** for async (not raw asyncio) to support multiple backends
- **Rich** for console output, **prompt_toolkit** for input
- Shell tool sets `MLG_CLI=1` env var for script detection
- Context files named `MLG.md` (discovered up directory tree)
- Custom exceptions inherit from `MlgError` base class

## Testing

```python
# Mock providers for unit tests
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

## Implementation Reference

See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) for the 12-phase implementation roadmap with detailed code examples for each component.
