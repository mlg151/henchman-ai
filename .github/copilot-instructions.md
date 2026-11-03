# Henchman-AI Copilot Instructions

Henchman-AI is a **model-agnostic AI agent CLI** in Python, inspired by gemini-cli, supporting DeepSeek, OpenAI-compatible APIs, Anthropic, Ollama, OpenRouter via one provider abstraction.

## Project Status
All 13 phases implemented (foundations, providers, agent loop, tools, built-in tools, configuration, terminal UI, sessions, MCP, extensions, advanced features, release tooling, multi-agent dev team).

## Architecture
```
src/henchman/
├── agents/  # Orchestrator, AgentPool, Identity, Prompts, Presets, Delegation, Ledger, Metrics
├── api/     # REST API
├── cli/     # Rich console, prompt_toolkit, slash commands
├── config/  # Pydantic settings, YAML, AgentConfig
├── core/    # Agent, EventBus, events, session
├── extensions/  # Extension ABC, ExtensionManager, /extensions
├── knowledge/  # Knowledge graph
├── mcp/      # McpClient, McpManager, McpTool
├── metrics/  # Metrics collection, storage, reporting
├── providers/ # OpenAICompatible base, DeepSeek, Anthropic, Ollama, OpenRouter
├── rag/      # Retrieval-augmented semantic code search
├── tools/    # Runtime-registered built-in/extension tools
└── utils/    # Utility helpers
```
`OpenAICompatibleProvider` covers any OpenAI-compatible API (DeepSeek, OpenAI, OpenRouter, Together, Groq, Fireworks); aliases like `together`/`groq`/`fireworks` use `openai_compat` with a configured base URL.

## Development Setup
```bash
uv sync --extra dev
uv run --extra dev python -m ruff check src tests
uv run --extra dev python -m mypy src
uv run --extra dev python -m pytest --cov-fail-under=90
uv run henchman --version
```

## CI & Quality
GitHub Actions tests Python 3.11–3.14, builds the wheel/sdist, and installs artifacts in clean smoke jobs; each must pass CLI help/unknown-command checks, API readiness, and a Chroma add/query round trip. An independent Python 3.12 job builds a wheel and runs `tests/testing/installed_wheel_smoke.py` outside the checkout.
- **90% minimum whole-project coverage** — changed behavior must be fully tested.
- **Type hints** — all signatures must be typed.
- **Linting** — pass ruff and mypy.

## Key Patterns

### Providers (Implemented)
```python
from henchman.providers import DeepSeekProvider, AnthropicProvider, OllamaProvider, Message
provider = DeepSeekProvider(api_key="your-key")
provider = AnthropicProvider(api_key="sk-ant-...", model="claude-sonnet-4-20250514")
provider = OllamaProvider(model="llama3.2")
async for chunk in provider.chat_completion_stream(
    messages=[Message(role="user", content="Hello")], tools=[...],
):
    if chunk.content: print(chunk.content, end="")
    if chunk.finish_reason: break
```
| Provider | API Key Env | Default Model | Notes |
|---|---|---|---|
| deepseek | `DEEPSEEK_API_KEY` | deepseek-chat | OpenAI-compatible, default |
| anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 | Native SDK |
| ollama | None | llama3.2 | Local models, OpenAI-compatible |
| openrouter | `OPENROUTER_API_KEY` | openai/gpt-4o-mini | Hundreds of models |
| openai_compat | Varies | (config required) | Any OpenAI-compatible API |
| together/groq/fireworks | respective keys | (config required) | `openai_compat` aliases |

Configs use names in parentheses; `henchman config set providers.default <name> --scope project` works in `settings.yaml`.

### Core Types, Registry & Agent Loop
```python
from henchman.providers import (Message, ToolCall, ToolDeclaration, StreamChunk, FinishReason)
provider = get_default_registry().create("deepseek", api_key="...", model="deepseek-chat")
from henchman.core import Agent, AgentEvent, EventType
agent = Agent(provider=provider, system_prompt="You are a helpful assistant.")
async for event in agent.run("Hello, world!"):
    if event.type == EventType.CONTENT: print(event.data, end="")
    elif event.type == EventType.TOOL_CALL_REQUEST:
        tool_call = event.data
        agent.submit_tool_result(tool_call.id, execute_tool(tool_call))
    elif event.type == EventType.FINISHED: break
async for event in agent.continue_with_tool_results(): ...
```
All LLM interactions stream via async generators (`AsyncIterator[StreamChunk]`).

### REPL, Tools & Config
```python
from henchman.cli import Repl, ReplConfig, OutputRenderer, parse_command
provider = DeepSeekProvider(api_key="...")
repl = Repl(provider=provider, config=ReplConfig(system_prompt="You are helpful", auto_save=True))
import anyio; anyio.run(repl.run)
renderer = OutputRenderer(); renderer.success("Done")
result = parse_command("/model gpt-4")  # ("model", ["gpt-4"])
from henchman.tools import Tool, ToolKind, ToolRegistry, ConfirmationRequest
registry = ToolRegistry(); registry.register(MyTool())
registry.set_confirmation_handler(confirm)  # ConfirmationRequest -> bool
from henchman.config import load_settings, ContextLoader
settings = load_settings(); context = ContextLoader().load()  # Concatenated HENCHMAN.md files
```
REPL: slash commands (/quit, /clear, /help, /tools), `@file` expansion, `!shell`, tool-call confirmation, Rich streaming. CLI: `henchman`, `henchman chat --prompt "..."`. Event types: `CONTENT`, `THOUGHT`, `TOOL_CALL_REQUEST`, `TOOL_CALL_RESULT`, `TOOL_CONFIRMATION`, `ERROR`, `FINISHED`. Tools: `ToolKind` auto-approval — `READ` auto-approved, `WRITE`/`EXECUTE`/`NETWORK` confirmed. Config precedence: defaults → user → workspace → env vars.

### Session, MCP & Extensions
```python
from henchman.core import SessionManager
manager = SessionManager()
manager.create_session(project_hash=manager.compute_project_hash(Path.cwd()), tag="my-feature")
manager.save(session)
from henchman.mcp import McpServerConfig, McpClient
serena = McpServerConfig(command="uvx", args=["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"], trusted=True)
client = McpClient(name="serena", config=serena_config)
await client.connect(); tools = await client.discover_tools()
await client.call_tool("find_symbol", {"name": "authenticate_user", "kind": "function"})
await client.disconnect()
from henchman.extensions import Extension, ExtensionManager
class MyExtension(Extension):  # name/version/description + get_tools/get_commands/get_context
manager = ExtensionManager(); manager.discover_entry_points()
```
Sessions persist JSON in `~/.henchman/sessions/`, scoped by `project_hash`. MCP commands: `/mcp list`, `/mcp status`; Serena recommended for semantic code analysis. Extensions register entry points in `pyproject.toml` or `~/.henchman/extensions/<name>/`.
**Serena MCP**: `find_symbol`, `find_referencing_symbols`, `insert_after_symbol`, 30+ languages, optional JetBrains. Install uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`), configure in `settings.yaml`, verify with `henchman` then `/mcp status` and `/tools`.

## Conventions
- Pydantic v2 for models/settings; anyio for async; Rich for console, prompt_toolkit for input, Click for CLI.
- Shell tool sets `HENCHMAN_CLI=1` for script detection; context files named `HENCHMAN.md`, discovered up the directory tree; custom exceptions inherit from `MlgError`; Google-style docstrings for public functions.

## Testing
Mock providers: `AsyncMock` provider with `chat_completion_stream` yielding `StreamChunk`; mark real-API tests with `@pytest.mark.integration`.

## Development Workflow
Test-Driven Development with strict quality gates: write tests first, implement minimum code to pass tests, then run `uv lock --check`, `ruff check src tests`, `mypy src`, `pytest --cov-fail-under=90`, `uv build`. Update docs and `FEATURE_TODO.md`/`TODOS.md` on user-facing changes; commit with a descriptive message. Prefer focused verification; reuse existing helpers and docs.
