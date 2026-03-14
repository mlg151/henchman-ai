# Henchman-AI Copilot Instructions

Henchman-AI is a **model-agnostic AI agent CLI** in Python, inspired by gemini-cli. It supports multiple LLM providers (DeepSeek, OpenAI/OpenAI-compatible APIs, Anthropic, Ollama, OpenRouter) via a unified provider abstraction.

## Project Status
- **Phase 1**: Project Foundation ✅
- **Phase 2**: Provider System ✅
- **Phase 3**: Core Agent Loop ✅
- **Phase 4**: Tool System ✅
- **Phase 5**: Built-in Tools ✅ (including ask_user tool)
- **Phase 6**: Configuration System ✅
- **Phase 7**: Terminal UI ✅
- **Phase 8**: Session Management ✅
- **Phase 9**: MCP Integration ✅
- **Phase 10**: Extensions & Plugins ✅
- **Phase 11**: Advanced Features ✅ (Multiple Providers, Headless mode, JSON output)
- **Phase 12**: Polish & Release ✅ (100% test coverage, all core features implemented)
- **Phase 13**: Multi-Agent Dev Team ✅ (Orchestrator, EventBus, Team Delegation)
## Architecture Overview
```
src/henchman/
├── agents/     # Multi-agent system: Orchestrator, AgentPool, Identity, Prompts, Presets, Delegation, Ledger, Metrics
├── api/        # REST API server for programmatic access
├── cli/        # UI layer: Rich console, prompt_toolkit input, slash commands (/agent, /team)
├── config/     # Pydantic settings, hierarchical YAML loading, AgentConfig
├── core/       # Agent layer: Agent, EventBus, events, session
├── extensions/ # Plugin system: Extension ABC, ExtensionManager, /extensions command
├── knowledge/  # Knowledge graph for project understanding and context
├── mcp/        # MCP integration: McpClient, McpManager, McpTool wrapper
├── metrics/    # Performance metrics collection, storage, and reporting
├── providers/  # Model providers: OpenAICompatible base, DeepSeek, Anthropic, Ollama, OpenRouter
├── rag/        # Retrieval-Augmented Generation for semantic code search
├── tools/      # Built-in tools (34 total): read_file, write_file, edit_file, shell, grep, etc.
└── utils/      # Utility functions and helpers
```
**Key insight**: The `OpenAICompatibleProvider` handles any OpenAI-compatible API including DeepSeek, OpenAI, OpenRouter, Together, Groq, Fireworks AI, and similar services. Specific providers like `together`, `groq`, and `fireworks` are aliases for `openai_compat` with appropriate base URLs.
## Development Setup
```bash
pip install -e ".[dev]"       # Install in editable mode with dev deps
./scripts/ci.sh               # Run full CI pipeline
henchman --version                 # Verify CLI entry point
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
from henchman.providers import DeepSeekProvider, AnthropicProvider, OllamaProvider, Message
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
| DeepSeek (`deepseek`) | `DEEPSEEK_API_KEY` | deepseek-chat | OpenAI-compatible, default provider |
| Anthropic (`anthropic`) | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 | Native SDK |
| Ollama (`ollama`) | None required | llama3.2 | Local models, OpenAI-compatible API |
| OpenRouter (`openrouter`) | `OPENROUTER_API_KEY` | openai/gpt-4o | OpenAI-compatible, access to hundreds of models |
| OpenAI-Compatible (`openai_compat`) | Varies by service | gpt-4o | Generic provider for ANY OpenAI-compatible API (OpenAI, Together, Groq, Fireworks, etc.) |
| Together AI (`together`) | `TOGETHER_API_KEY` | meta-llama/Llama-3.3-70B-Instruct-Turbo | OpenAI-compatible (alias for openai_compat with Together base URL) |
| Groq (`groq`) | `GROQ_API_KEY` | llama-3.3-70b-specdec | OpenAI-compatible (alias for openai_compat with Groq base URL) |
| Fireworks AI (`fireworks`) | `FIREWORKS_API_KEY` | accounts/fireworks/models/llama-v3p1-70b-instruct | OpenAI-compatible (alias for openai_compat with Fireworks base URL) |
### Core Types
```python
from henchman.providers import (
Message,           # Conversation message (role, content, tool_calls)
ToolCall,          # Tool invocation request (id, name, arguments)
ToolDeclaration,   # Tool schema for LLM (name, description, parameters)
StreamChunk,       # Streaming response (content, tool_calls, finish_reason)
FinishReason,      # STOP, TOOL_CALLS, LENGTH, CONTENT_FILTER
)
```
### Provider Registry
```python
from henchman.providers import get_default_registry
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
from henchman.core import Agent, AgentEvent, EventType
from henchman.providers import DeepSeekProvider
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
from henchman.cli import Repl, ReplConfig
from henchman.providers import DeepSeekProvider
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
henchman
# Headless mode (single prompt)
henchman --prompt "What is 2+2?"
henchman -p "Summarize this file: @document.txt"
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
from henchman.tools import Tool, ToolKind, ToolResult, ToolRegistry, ConfirmationRequest
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
from henchman.config import load_settings, Settings, ContextLoader
# Load settings (automatically discovers and merges files)
settings = load_settings()
# Access provider settings
print(settings.providers.default)  # "deepseek"
print(settings.providers.deepseek)  # {"model": "deepseek-chat"}
# Access tool settings
print(settings.tools.shell_timeout)  # 60
print(settings.tools.auto_approve_read)  # True
# Load context files (HENCHMAN.md)
loader = ContextLoader()
context = loader.load()  # Concatenated content from all HENCHMAN.md files
```
**Settings Precedence** (later overrides earlier):
1. Defaults (Pydantic model defaults)
2. User settings (`~/.henchman/settings.yaml`)
3. Workspace settings (`.henchman/settings.yaml`)
4. Environment variables (`HENCHMAN_PROVIDER`, `HENCHMAN_MODEL`)
**Context File Discovery** (HENCHMAN.md):
- Global: `~/.henchman/HENCHMAN.md`
- Ancestors: Walk up from cwd to git root
- Subdirectories: Optional, respects `.gitignore`
### Terminal UI (Implemented)
The CLI provides a Rich-based terminal interface with theming and commands:
```python
from henchman.cli import OutputRenderer, Theme, ThemeManager
from henchman.cli.commands import CommandRegistry, parse_command
from henchman.cli.commands.builtins import get_builtin_commands
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
from henchman.cli import is_slash_command, is_shell_command, expand_at_references
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
from henchman.core import Session, SessionManager, SessionMessage, SessionMetadata
# Create a session manager
manager = SessionManager()  # Uses ~/.henchman/sessions by default
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
- Sessions stored as JSON in `~/.henchman/sessions/`
- Each session is `{session_id}.json`
- Scoped by project_hash to isolate per-project
### MCP Integration (Implemented)
MCP (Model Context Protocol) enables connecting to external tool servers:
```python
from henchman.mcp import McpServerConfig, McpClient, McpManager, McpTool

# Configure MCP servers (filesystem, github, serena, etc.)
filesystem_config = McpServerConfig(
    command="npx",
    args=["@anthropic-ai/mcp-filesystem-server", "/home/user"],
    trusted=False,  # Untrusted servers require tool confirmation
)

github_config = McpServerConfig(
    command="uvx",
    args=["mcp-github"],
    env={"GITHUB_TOKEN": "your-token-here"},
    trusted=True,
)

# RECOMMENDED: Serena for semantic code analysis
serena_config = McpServerConfig(
    command="uvx",
    args=["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"],
    trusted=True,  # Serena tools are safe for auto-approval
)

# Connect to a single server
client = McpClient(name="serena", config=serena_config)
await client.connect()
tools = await client.discover_tools()
# Use Serena's semantic tools
result = await client.call_tool("find_symbol", {
    "name": "authenticate_user",
    "kind": "function"
})
await client.disconnect()

# Or manage multiple servers
configs = {
    "filesystem": filesystem_config,
    "github": github_config,
    "serena": serena_config,  # Highly recommended for coding tasks
}
manager = McpManager(configs)
await manager.connect_all()
all_tools = manager.get_all_tools()  # List[McpTool]
await manager.disconnect_all()
```
**MCP Configuration (settings.yaml):**
```yaml
mcp_servers:
  # File system access
  filesystem:
    command: npx
    args: ["@anthropic-ai/mcp-filesystem-server", "/home/user"]
    trusted: false
  
  # GitHub integration
  github:
    command: uvx
    args: ["mcp-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    trusted: true
  
  # Serena - Semantic code retrieval and editing (RECOMMENDED)
  serena:
    command: uvx
    args: ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"]
    env:
      # Optional: Set workspace directory (defaults to current directory)
      SERENA_WORKSPACE: "${PROJECT_ROOT}"
      # Optional: Enable JetBrains plugin backend if available
      SERENA_USE_JETBRAINS: "false"
    trusted: true
    # Note: Serena requires uv to be installed: https://docs.astral.sh/uv/
  
  # Optional: Add more MCP servers as needed
  # postgres:
  #   command: npx
  #   args: ["@modelcontextprotocol/server-postgres", "postgresql://user:pass@localhost/db"]
  #   trusted: false
```
**MCP Commands:**
- `/mcp list` - List configured MCP servers and connection status
- `/mcp status` - Show connection status and available tools

### Serena MCP Server Integration

**Serena** is a powerful coding agent toolkit that provides semantic code retrieval and editing capabilities via MCP. It enhances coding agents with IDE-like tools for efficient code navigation and manipulation.

#### Key Features of Serena:
- **Semantic Code Retrieval**: Find symbols, functions, classes by name with context
- **Precise Code Editing**: Insert, replace, or delete code at symbol level
- **Cross-Reference Analysis**: Find referencing symbols and dependencies
- **Multi-Language Support**: 30+ programming languages via LSP backends
- **JetBrains Integration**: Optional plugin for enhanced analysis capabilities

#### Serena Tools Available via MCP:
```python
# Example Serena tool usage
result = await client.call_tool("find_symbol", {
    "name": "authenticate_user",
    "kind": "function"
})

result = await client.call_tool("find_referencing_symbols", {
    "symbol_id": "function:authenticate_user:42"
})

result = await client.call_tool("insert_after_symbol", {
    "symbol_id": "function:authenticate_user:42",
    "content": "    # Added logging\n    logger.info(f\"User authenticated: {username}\")"
})
```

#### Setting Up Serena:
1. **Install uv** (required for Serena):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Configure in settings.yaml** (as shown above)

3. **Start Henchman-AI** - Serena will auto-connect if configured

4. **Verify connection**:
   ```bash
   henchman
   /mcp status  # Check if Serena is connected
   /tools       # List available tools including Serena's
   ```

#### When to Use Serena:
- **Large codebases**: Efficient navigation without reading entire files
- **Refactoring tasks**: Precise symbol-level edits
- **Code understanding**: Cross-reference analysis and dependencies
- **Complex implementations**: Semantic search for relevant code patterns

#### Performance Benefits:
- **Reduces token usage**: Semantic retrieval vs. reading entire files
- **Improves accuracy**: Symbol-level precision over string matching
- **Enhances productivity**: IDE-like capabilities in the CLI
- **Scales with codebase**: Efficient even in large, complex projects

#### Example Workflow with Serena:
```python
# Without Serena: Read entire files, grep for patterns
files = await glob("**/*.py")
for file in files:
    content = await read_file(file)  # Inefficient for large codebases
    if "authenticate" in content:
        # Manual analysis needed

# With Serena: Semantic search
symbols = await serena_client.call_tool("find_symbol", {
    "name": "authenticate",
    "kind": ["function", "method"]
})
# Returns precise locations and contexts
```

#### Configuration Options:
```yaml
serena:
  command: uvx
  args: ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"]
  env:
    # Workspace directory (default: current directory)
    SERENA_WORKSPACE: "/path/to/project"
    
    # Backend selection: "lsp" or "jetbrains" (if plugin installed)
    SERENA_BACKEND: "lsp"
    
    # Language server configuration
    SERENA_LSP_PYTHON_PATH: "/usr/bin/python3"
    
    # Logging level
    SERENA_LOG_LEVEL: "INFO"
  trusted: true
```

#### Troubleshooting:
- **"uvx not found"**: Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Connection failed**: Check `uvx --version` and internet connectivity
- **No tools discovered**: Verify Serena starts correctly with `uvx --from git+https://github.com/oraios/serena serena start-mcp-server --help`
- **Performance issues**: Consider using JetBrains plugin backend for better analysis

**Key Types:**
- `McpServerConfig` - Server configuration (command, args, env, trusted)
- `McpClient` - Single server connection manager
- `McpManager` - Multi-server connection manager
- `McpTool` - Wraps MCP tools as internal Tool instances
- `McpToolResult` - Result from MCP tool execution
### Extensions System (Implemented)
Extensions allow third-party plugins to add tools, commands, and context:
```python
from henchman.extensions import Extension, ExtensionManager
from henchman.tools.base import Tool
from henchman.cli.commands import Command
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
manager.discover_directory(Path.home() / ".henchman" / "extensions")
```
**Extension Discovery:**
- Entry points: Register in `pyproject.toml` under `[project.entry-points."henchman.extensions"]`
- Directory: Place `extension.py` with Extension subclass in `~/.henchman/extensions/<name>/`
**Built-in Commands:**
- `/extensions` - List loaded extensions with name, version, and description

## Performance Optimization & Agent Effectiveness

### Agent Performance Improvement Framework

To maximize agent effectiveness and efficiency, follow these structured approaches:

#### 1. Working Memory System
Maintain context efficiently to reduce file re-reading (target: 60% reduction from 3.2 to 1.3 re-reads per task):

```yaml
# Working Memory Template (UPDATE AFTER EACH ACTION - VERIFICATION REQUIRED)
working_memory:
  current_task: "string describing active task"
  task_objectives: ["specific", "goals", "for", "task"]
  recent_files:
    - path: "file/path.py"
      purpose: "why this file was read"
      timestamp: "ISO timestamp"
      lines_read: "start_line-end_line or 'full'"
      key_insights: ["important", "findings", "from", "file"]
  active_context:
    project_structure: "brief description"
    relevant_patterns: ["patterns", "from", "knowledge", "graph"]
    constraints: ["known", "limitations"]
    dependencies: ["required", "components"]
  decisions_made:
    - decision: "key decision"
      rationale: "why this decision"
      impact: "high|medium|low"
  completed_steps: ["step1", "step2"]
  next_actions:
    - action: "next step"
      priority: "high|medium|low"
      estimated_effort: "time estimate"
  insights_gained: ["new", "learnings"]
  problems_encountered:
    - problem: "issue encountered"
      status: "open|in_progress|resolved"
      resolution: "how it was fixed"
```

**Memory Update Protocol**:
1. After reading a file → Add to `recent_files` with purpose and lines_read
2. After making a decision → Add to `decisions_made` with rationale and impact
3. After completing a step → Add to `completed_steps`
4. When planning next steps → Update `next_actions`
5. When learning something new → Add to `insights_gained`
6. When encountering a problem → Add to `problems_encountered`

**Verification Requirements for Working Memory**:
- ✅ **Before reading a file**: Check `recent_files` to avoid re-reading
- ✅ **After each action**: Update working memory immediately
- ✅ **Every 5 tool calls**: Review and prune `recent_files` (keep last 10)
- ✅ **Task completion**: Archive working memory to `.agent_tasks/<task>/working_memory.yaml`
- ✅ **Metrics tracking**: Count file reads and compare to baseline (target < 1.3 re-reads/task)

**Common Anti-Patterns to Avoid**:
❌ **Sequential Re-reading Without Context Retention**: Check `recent_files` before reading
❌ **Full File Reads for Partial Information**: Use targeted line ranges
❌ **Redundant Cross-Referencing**: Cache relationships in `active_context`
❌ **Test-Driven Over-Reading**: Reference test patterns from `relevant_patterns`

#### 2. Smart File Reading Strategies
Optimize file reading to avoid context window waste (target: 68% reduction from 250 to 80 lines per file):

**Based on Baseline Analysis of 6 Inefficient Patterns**:
1. **Sequential Re-reading Without Context Retention** → Use working memory cache
2. **Full File Reads for Partial Information** → Use targeted line ranges  
3. **Lack of Strategic Reading Order** → Follow reading patterns below
4. **Missing File Size Awareness** → Apply size-based guidelines
5. **Redundant Cross-Referencing** → Cache relationships in working memory
6. **Test-Driven Over-Reading** → Use test-specific patterns

**Pattern 1: Initial Exploration** (new file - addresses pattern #3)
```python
# Read first 50 lines for overview, check working memory first
if path in working_memory.recent_files:
    # Use cached insights, read only new sections if needed
    content = await read_file(path, start_line=1, end_line=50)
```

**Pattern 2: Error Analysis** (debugging - addresses pattern #2)
```python
# Read lines around error (error_line ± 10), not entire file
context = await read_file(path, start_line=max(1, error_line-10), end_line=error_line+10)
```

**Pattern 3: Function/Class Analysis** (addresses pattern #2)
```python
# Find definition, then read specific function only
definition_line = await find_definition(path, "function_name")
if definition_line:
    # Read function + 10 lines after for context
    content = await read_file(path, start_line=definition_line, end_line=definition_line+50)
```

**Pattern 4: Recent Changes** (addresses pattern #5)
```python
# Read last 100 lines for recent activity, not entire history
recent = await read_file(path, start_line=-100, end_line=-1)
```

**Pattern 5: Structure Analysis** (addresses pattern #2)
```python
# Read only imports and definitions, not implementation details
imports = await grep("^import |^from ", path)
classes = await grep("^class ", path)
functions = await grep("^def ", path)
```

**Pattern 6: Test-Specific Reading** (addresses pattern #6)
```python
# For test files: read test class/function + setup/teardown only
test_context = await read_file(path, start_line=test_start_line, end_line=test_end_line+20)
```

**Pattern 7: Configuration Reading** (addresses pattern #2)
```python
# For config files: read specific sections using grep
section = await grep("^\[database\]", path)
if section:
    # Read only the database section
    content = await read_file(path, start_line=section_line, end_line=section_line+20)
```

**Pattern 8: Dependency Analysis** (addresses pattern #5)
```python
# Read imports and first-level dependencies only
imports = await read_file(path, start_line=1, end_line=30)  # Usually at top
```

**File Size Guidelines** (addresses pattern #4):
- **< 100 lines** → Read entire file (safe for context)
- **100-500 lines** → Read targeted sections (use line ranges)
- **500-1000 lines** → ALWAYS use line ranges, read max 100 lines at once
- **> 1000 lines** → Use grep/pattern matching first, then targeted reads
- **> 10000 lines** → Consider alternative approaches (Serena MCP, chunked reading)

**Strategic Reading Order** (addresses pattern #3):
1. **First**: Check working memory for existing context
2. **Second**: Read project structure files (pyproject.toml, README)
3. **Third**: Read imports and class definitions
4. **Fourth**: Read specific functions/methods as needed
5. **Fifth**: Read tests and documentation last

**Verification Requirements**:
- ✅ **Before each read**: Check if file is in `recent_files` (avoid re-reads)
- ✅ **Size check**: Apply size-based guidelines before reading
- ✅ **Line ranges**: Always specify `start_line`/`end_line` for files > 100 lines
- ✅ **Purpose tracking**: Record why file was read in `recent_files.purpose`
- ✅ **Efficiency metric**: Target < 80 lines read per file (from 250 baseline)

#### 3. Structured Thinking Protocols
**REQUIRED FOR ALL COMPLEX TASKS**:

```
THINKING PROTOCOL:

## Phase 1: Problem Analysis
1. What exactly needs to be solved? (Be specific)
2. What are the success criteria? (How will we know we're done?)
3. What constraints exist? (Time, resources, dependencies)

## Phase 2: Context Gathering
4. What do we already know? (Check knowledge graph, recent files)
5. What similar problems have we solved? (Search .agent_tasks/)
6. What tools are available? (Review tool capabilities)

## Phase 3: Solution Design
7. What are possible approaches? (Generate 2-3 options)
8. What are the pros/cons of each? (Risk assessment)
9. Which approach is best? (Decision with rationale)

## Phase 4: Execution Planning
10. What specific steps are needed? (Break down into actionable items)
11. What could go wrong? (Risk mitigation)
12. How will we verify success? (Validation criteria)
```

#### 4. Delegation Optimization
**Delegation Decision Matrix** (USE BEFORE ANY WORK):

| Task Type              | Primary Specialist | When to Delegate                |
|------------------------|-------------------|---------------------------------|
| Architecture/Design    | Planner           | Always for complex designs      |
| Research/Exploration   | Explorer          | When new information is needed  |
| Implementation/Testing | Engineer          | For coding tasks > 10 lines     |
| Documentation          | Explorer          | For comprehensive documentation|
| Debugging             | Engineer          | For complex bugs                |

**Delegation Checklist** (If ANY answer is YES → DELEGATE):
1. ✅ Is this a specialized task type?
2. ✅ Would a specialist do this better/faster?
3. ✅ Can I provide clear requirements?
4. ✅ Is the specialist available/appropriate?

#### 5. Performance Metrics Tracking
Track effectiveness for continuous improvement:

```markdown
## Performance Metrics Dashboard

### Efficiency Metrics
- **Task Completion Time**: [start] to [end] = [duration]
- **Files Accessed**: [count] files read/written
- **Tool Usage**: [count] by tool type
- **Delegation Rate**: [delegations]/[total tasks] = [percentage]

### Quality Metrics
- **Test Results**: [passing]/[total] tests = [percentage]
- **Code Coverage**: [coverage percentage]
- **Linting Status**: [errors]/[warnings]
- **Documentation Coverage**: [documented]/[total] public APIs

### Target Performance Metrics
- File re-reads per task: Target < 1.3 (60% reduction from 3.2)
- Delegation rate: Target > 40% (from current 25%)
- Error rate: Target reduction of 50%
- Context window usage: Target < 40% (from 65%)
```

#### 6. Pre-flight Checklists
**Before Running Tests**:
- [ ] Test database is clean and seeded
- [ ] Environment variables are set
- [ ] Dependencies are installed
- [ ] No pending migrations
- [ ] Test isolation is configured

**Before File Modification**:
- [ ] Read existing tests for the file
- [ ] Check for dependent modules
- [ ] Create backup/checkpoint
- [ ] Verify understanding of requirements
- [ ] Plan rollback strategy

**Before Delegation**:
- [ ] Requirements are clearly documented
- [ ] Success criteria are explicit
- [ ] Context is complete
- [ ] Files to modify are specified
- [ ] Done_when condition is verifiable

#### 7. Tool Combination Patterns
Optimize tool usage with effective sequences:

**Research Task Pattern**:
1. `rag_search` - Find related code
2. `read_file` - Examine key files
3. `kg_query` - Check knowledge graph
4. `web_search` - External research if needed
5. `write_file` - Document findings

**Debugging Task Pattern**:
1. `grep` - Find error patterns
2. `read_file` - Examine error location
3. `shell` - Run specific test
4. `kg_query` - Find related code
5. `edit_file` - Fix the issue

**Implementation Task Pattern**:
1. `read_file` - Understand existing code
2. `write_file` - Create test stubs
3. `edit_file` - Implement functionality
4. `shell` - Run tests
5. `write_file` - Update documentation

#### 8. Learning Database Integration
Capture and reuse successful patterns:

```markdown
# .agent_tasks/patterns/ directory structure
patterns/
├── successful_approaches.md      # What worked well
├── common_errors.md              # What to avoid
├── tool_combinations.md          # Effective tool sequences
├── debugging_patterns.md         # Problem-solving approaches
└── decision_frameworks.md        # How to make specific decisions

# Example pattern entry:
## Pattern: Debugging Test Failures
**When to use**: When pytest fails unexpectedly
**Steps**:
1. Run specific test: `pytest tests/path/test.py::test_name -xvs`
2. Check recent changes: `git diff HEAD~3`
3. Examine imports: Look for circular dependencies
4. Check environment: Verify required variables
**Success Rate**: 85% (from 20 instances)
**Last Updated**: 2024-01-15
```

### Performance Improvement Targets

#### Week 1: Context Management
- **Goal**: Reduce file re-reads by 60%
- **Focus**: Working memory system, smart reading patterns
- **Success Metric**: File reads per task < 1.3 (from 3.2)

#### Week 2: Thinking & Delegation
- **Goal**: Increase delegation rate to 40%
- **Focus**: Structured thinking protocols, delegation optimization
- **Success Metric**: Delegation rate > 40% (from 25%)

#### Week 3: Metrics & Learning
- **Goal**: Implement quantitative performance tracking
- **Focus**: Metrics dashboard, learning database
- **Success Metric**: All metrics tracked and reported

#### Week 4: Optimization
- **Goal**: Reduce error rate by 50%
- **Focus**: Pre-flight checklists, tool combination patterns
- **Success Metric**: Error rate reduction of 50%

### Common Anti-Patterns to Avoid

❌ **Reading entire large files** → Use line ranges
❌ **Repeated full reads** → Use working memory cache
❌ **Reading without purpose** → Have clear goal before reading
❌ **Not delegating specialized work** → Use delegation matrix
❌ **Skipping thinking phase** → Always use thinking protocol
❌ **Not tracking metrics** → Update performance dashboard

### Quick Reference

**Before starting work**:
1. Check working memory for existing context
2. Use thinking protocol for complex tasks
3. Consult delegation matrix for specialist work
4. Apply appropriate file reading pattern

**During work**:
1. Update working memory after each action
2. Track metrics for performance measurement
3. Document insights in learning database
4. Use tool combination patterns

**After work**:
1. Archive completed task to knowledge graph
2. Update performance metrics
3. Record successful patterns
4. Clean working memory for next task

## Conventions
- **Pydantic v2** for all data models and settings schemas
- **anyio** for async (not raw asyncio) to support multiple backends
- **Rich** for console output, **prompt_toolkit** for input
- **Click** for CLI framework
- Shell tool sets `HENCHMAN_CLI=1` env var for script detection
- Context files named `HENCHMAN.md` (discovered up directory tree)
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
henchman-ai/
├── src/henchman/                    # Main package
│   ├── __init__.py             # Package init, exports __version__
│   ├── __main__.py             # Entry point for python -m henchman
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
│   │   └── context.py          # ContextLoader for HENCHMAN.md files
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
│       ├── security.py         # Security validation
│       └── builtins/           # 34 built-in tools
│           ├── ask_user.py     # AskUserTool - ask user questions
│           ├── code_format.py  # CodeFormatTool - ruff formatting
│           ├── coverage_map.py # CoverageMapTool - parse coverage reports
│           ├── dead_code.py    # DeadCodeTool - detect unused code
│           ├── deep_research.py # DeepResearchTool - end-to-end web research
│           ├── delegate.py     # DelegateTaskTool - delegate to specialists
│           ├── diff_view.py    # DiffViewTool - show git diffs
│           ├── env_inspect.py  # EnvInspectTool - inspect Python environment
│           ├── file_edit.py    # EditFileTool - surgical file edits
│           ├── file_overview.py # FileOverviewTool - structural file summary
│           ├── file_read.py    # ReadFileTool - read file contents
│           ├── file_write.py   # WriteFileTool - write to files
│           ├── git_ops.py      # GitOpsTool - git operations
│           ├── glob_tool.py    # GlobTool - find files by pattern
│           ├── grep.py         # GrepTool - search file contents
│           ├── import_graph.py # ImportGraphTool - analyze dependencies
│           ├── kg_query.py     # KgQueryTool - query knowledge graph
│           ├── kg_update.py    # KgUpdateTool - update knowledge graph
│           ├── lint_check.py   # LintCheckTool - ruff/mypy linting
│           ├── ls.py           # LsTool - list directory contents
│           ├── patch_apply.py  # PatchApplyTool - apply unified diffs
│           ├── pattern_search.py # PatternSearchTool - natural language code search
│           ├── pip_inspect.py  # PipInspectTool - query packages
│           ├── pytest_run.py   # PytestRunTool - run pytest tests
│           ├── python_ast.py   # PythonAstTool - parse Python AST
│           ├── python_exec.py  # PythonExecTool - execute Python code
│           ├── rag_search.py   # RagSearchTool - semantic code search
│           ├── research_notes.py # ResearchNotesTool - persistent note-taking
│           ├── shell.py        # ShellTool - execute shell commands
│           ├── symbol_trace.py # SymbolTraceTool - trace symbol provenance
│           ├── test_gen.py     # TestGenTool - generate test stubs
│           ├── traceback_parse.py # TracebackParseTool - parse tracebacks
│           ├── web_fetch.py    # WebFetchTool - fetch web content
│           └── web_search.py   # WebSearchTool - search the web
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
3. Implement feature in `src/henchman/`
4. Add exports to `__init__.py` files
5. Run `./scripts/ci.sh` until all checks pass
6. Update relevant documentation
## Implementation Reference
See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) for the 12-phase implementation roadmap with detailed code examples for each component.


**Agent Workspace — `.agent_tasks/` Convention (MANDATORY)**:
All non-source artifacts (analysis scripts, design docs, research notes, validation reports, scratch files) MUST be placed inside the `.agent_tasks/` directory in the project root. NEVER create these files in the repo root or alongside source code.

Structure:
```
.agent_tasks/
├── <task-slug>/            # One folder per task or project
│   ├── README.md           # Task description, status, and findings
│   ├── analysis/           # Analysis scripts, notebooks, data exploration
│   ├── docs/               # Design docs, RFCs, research notes
│   └── scripts/            # Utility/validation/automation scripts
```

Rules:
1. Create `.agent_tasks/` if it doesn't exist.
2. Use a short, descriptive slug for each task folder (e.g., `elo-parameter-tuning`, `api-migration`).
3. Include a `README.md` in each task folder summarizing the goal and current status.
4. Source code changes go in the normal project directories — only supporting artifacts go here.
5. If a prior task folder exists for the same topic, reuse it instead of creating a new one.
6. ALWAYS KEEP THIS DOCUMENTATION UP TO DATE. If you create or modify files in the project, update the README with what you did and what you found.
7. We update this documentation before we work, while we work, and after we work. It is our single source of truth for what we've done and what we know.