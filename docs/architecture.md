# System Architecture

## Overview

Henchman-AI is built with a modular, component-based architecture that separates concerns and promotes maintainability. The system is designed around the principle of single responsibility, with each component handling a specific aspect of the CLI's functionality.

This architecture includes both shipped runtime paths and narrower integration seams. The shared discovery capability matrix is authoritative: local skills are local-only; integration blueprints (including Slack) are export-only; `schedule_cron` is metadata-only; remote agent/plugin installs are unavailable; the GitHub webhook helper is docs-only; and Tier 10 dialogs are intentionally absent from generic discovery even though they ship inside `henchman chat --tui`.

`ask_user` is runtime-dependent: classic REPL and Textual supply asynchronous
input handlers; headless and standalone tools remain unbound by default. See
[tool input behavior](tools.md#ask_user) for cancellation and session semantics.

Response-format checks observe optional legacy planning metrics without adding
synthetic user messages. Normal top-level conversation reports `responded` when
the current turn produces visible text, stops normally, and attempts no tools.
Empty replies, private reasoning, old messages, failed tool attempts, and abnormal
finishes cannot satisfy that response contract. A promise can be a response; it
is not evidence that the promised work happened.

Orchestrator completion status describes observed execution, not verified task
correctness. Provider errors and abnormal finishes (including length limits and
content filtering) report `failed`, even after successful tool calls. Loop evidence
belongs to the specific agent; nested tool results do not count as parent actions.
Delegated reports cannot overwrite the runtime status. Delegations default to
`completion_requirement="actions"`, which requires successful tool evidence;
an answer alone remains `no_work_done`. The lead may explicitly select `response`
for advice or analysis based on supplied context. Only that explicit requirement
allows `responded` to satisfy a delegation. Missing or unknown status and observed
runtime errors are unsuccessful. Both terminal UIs show
unsuccessful or unknown outcomes explicitly. Headless text runs exit 1 for failed,
stalled, or timed-out execution, and retain exit 2 for `no_work_done`.
Completion events separately include `task_verified: false` and an `evidence`
object with attempted/successful tool counts, whether the final response was
complete, and the selected requirement (or `null` if runtime evidence is absent).
The current `completed` status means execution included successful tools; it still
does not prove that an implementation changed the required behavior or passed
suitable verification. Neither counters nor specialist prose can establish that.
The UI therefore says “finished execution.” [Typed acceptance checks](tools.md#plan-acceptance-checks)
provide historical file, command, and pytest observations; whole-task correctness
and requirements coverage remain roadmap work. See [orchestrator API](api.md#orchestrator)
and [JSON output semantics](providers.md#streaming-reliability).

Headless JSON uses the same orchestrator as interactive execution, including
specialist provider selection and delegation policy checks. Agent-attributed
events preserve nested activity as it occurs, with consumer backpressure and
explicit closure of nested streams; `scope: "run"` marks the authoritative outer
completion. The JSON adapter emits one final `finished` event and rejects a
missing or unsuccessful outer outcome. Provider tool rounds have a finite budget
for both lead and specialist agents, independent of delegation call/depth limits.

Tool scopes use a live view of the runtime registry with fixed role allowlists.
The leader uses the same scope mechanism as specialists. Allowed late tools and
parent replacements are resolved through one lookup shared by declarations,
discovery and authorization; local overrides and exclusions stay local. Builtin
search instances bind separately to each scope. CLI fallback executors use the
acting agent's registry. See [agent tool scopes](agents.md#tool-scopes-and-late-registration).

## Core Architecture

### High-Level Component Diagram

```mermaid
graph TB
    User([User Input]) --> InputHandler
    InputHandler --> REPL[REPL Orchestrator]
    REPL --> CommandProcessor
    REPL --> ToolExecutor
    REPL --> OutputHandler
    REPL --> UIRenderer[UI Renderer]
    REPL --> PluginManager[Plugin Manager]
    REPL --> McpManager[MCP Manager]
    REPL --> SessionManager[Session Manager]
    REPL --> Orchestrator[Multi-Agent Orchestrator]
    
    CommandProcessor --> OutputHandler
    ToolExecutor --> OutputHandler
    OutputHandler --> User([User Output])
    
    Orchestrator --> AgentPool[Agent Pool]
    Orchestrator --> EventBus[Event Bus]
    
    ToolExecutor --> ToolManager[Tool Manager]
    ToolManager --> ToolRegistry[Tool Registry]
    
    subgraph "REPL Components"
        InputHandler
        OutputHandler
        CommandProcessor
        ToolExecutor
        UIRenderer
        PluginManager
        McpManager
        SessionManager
    end
    
    subgraph "Multi-Agent Dev Team"
        Orchestrator
        AgentPool
        EventBus
    end
    
    subgraph "Tool System"
        ToolManager
        ToolRegistry
    end
```

## Component Details

### REPL (Read-Eval-Print Loop)

**Location**: `src/henchman/cli/repl.py`  
**Role**: Main orchestrator and coordinator

The REPL class is the central coordinator that initializes and connects all components. It manages the main interaction loop and delegates work to specialized components.

**Responsibilities**:
- Initialize all component instances
- Manage the main interaction loop (`run()` method)
- Delegate input processing to `InputHandler`
- Delegate output handling to `OutputHandler` and `UIRenderer`
- Delegate command execution to `CommandProcessor`
- Delegate tool execution to `ToolExecutor`
- Manage plugins via `PluginManager`
- Manage MCP servers via `McpManager`
- Handle sessions via `SessionManager`
- Maintain backward compatibility with existing API

**Key Methods**:
- `__init__()`: Initialize all components
- `run()`: Main interaction loop
- `process_input()`: Route input to appropriate handler
- `_run_agent()`: Coordinate agent execution
- `_init_renderer()`: Initialize UI renderer
- `_init_tool_manager()`: Initialize tool system
- `_init_mcp_manager()`: Initialize MCP connections
- `_init_plugin_manager()`: Load plugins
- `_init_orchestrator()`: Create multi-agent system
- `_init_handlers()`: Initialize output and command handlers
- `_init_tool_executor()`: Initialize tool execution
- `_init_input_handler()`: Initialize input handling

### UIRenderer

**Location**: `src/henchman/cli/ui_renderer.py`  
**Role**: Rich console output and UI rendering

Handles all rich console output including formatting, progress bars, and status displays.

**Responsibilities**:
- Render rich console output with themes
- Display progress bars and status indicators
- Handle thinking indicators and animations
- Manage console formatting and styling
- Support accessible mode for screen readers

**Key Methods**:
- `print_welcome()`: Display welcome message
- `print_goodbye()`: Display exit message
- `start_thinking()`: Show thinking indicator
- `stop_thinking()`: Hide thinking indicator
- `show_thinking()`: Display thinking content
- `print_newline()`: Print blank line with proper styling

### InputHandler

**Location**: `src/henchman/cli/input_handler.py`  
**Role**: User input processing and management

Handles all aspects of user input including prompt sessions, history, and input validation.

**Responsibilities**:
- Manage `prompt_toolkit` prompt sessions
- Handle @file expansion (e.g., `@filename.txt`)
- Detect slash commands (e.g., `/quit`, `/clear`)
- Process keyboard interrupts (Ctrl+C) and EOF (Ctrl+D)
- Validate and sanitize user input
- Support custom keybindings from settings

**Key Methods**:
- `initialize_prompt_session()`: Set up prompt session with toolbar
- `get_input()`: Get user input with error handling
- `process_input()`: Process and classify input
- `is_slash_command()`: Detect command vs regular input
- `expand_at_references()`: Expand @file references

### OutputHandler

**Location**: `src/henchman/cli/output_handler.py`  
**Role**: Console output, status display, and event streaming

Manages all console output including rich formatting, status bars, and event display.

**Responsibilities**:
- Display welcome and goodbye messages
- Show status bars with provider/model information
- Display tool counts and MCP server status
- Handle event streaming from agents
- Show turn status with progress indicators
- Manage RAG background indexing status
- Coordinate with `UIRenderer` for actual output

**Key Methods**:
- `print_welcome()`: Display welcome message
- `print_goodbye()`: Display exit message
- `get_toolbar_status()`: Generate status bar content
- `create_status()`: Create rich status context manager
- `show_turn_status()`: Display turn progress

### CommandProcessor

**Location**: `src/henchman/cli/command_processor.py`  
**Role**: Slash command execution and management

Processes all slash commands and delegates to appropriate command handlers.

**Responsibilities**:
- Parse and validate slash commands
- Route commands to registered command handlers
- Handle built-in commands (`/quit`, `/clear`, `/help`, `/tools`, `/mcp`, `/extensions`)
- Support command arguments and options
- Provide error handling for invalid commands
- Integrate with plugin command system

**Key Methods**:
- `handle_command()`: Process a slash command
- `get_command_registry()`: Access command registry
- Command-specific handlers for built-in commands

### ToolExecutor

**Location**: `src/henchman/cli/tool_executor.py`  
**Role**: Tool execution and agent coordination

Executes tool calls from agents and manages tool confirmation workflows.

**Responsibilities**:
- Execute tool calls from agent streams
- Handle tool confirmation requests
- Manage tool iteration limits and cancellation
- Process agent event streams
- Coordinate with `ToolManager` for tool execution
- Handle tool retry logic and error recovery

**Key Methods**:
- `process_agent_stream()`: Process agent event stream
- `execute_tool_calls()`: Execute batch of tool calls
- `handle_tool_call()`: Handle single tool call
- `handle_confirmation()`: Process tool confirmation requests

### ToolManager

**Location**: `src/henchman/cli/tool_manager.py`  
**Role**: Tool registration and management

Manages the tool registry and provides tool-related services.

**Responsibilities**:
- Register built-in tools
- Manage tool confirmation policies
- Handle auto-approve settings
- Provide tool declarations for LLMs
- Integrate with MCP tools

**Key Methods**:
- `register_builtin_tools()`: Register all built-in tools
- `set_confirmation_handler()`: Set tool confirmation handler
- `set_auto_approve()`: Configure auto-approve behavior
- `set_plan_mode()`: Enable/disable plan mode

### PluginManager

**Location**: `src/henchman/cli/plugins.py`  
**Role**: Local plugin loading and management

Manages plugin discovery, loading, and integration.

This local manager is distinct from the unavailable remote marketplace-install surface. Registry client and installer classes are extension seams and do not imply a deployed marketplace backend.

**Responsibilities**:
- Discover plugins in configured directories
- Load and initialize plugins
- Register plugin tools and commands
- Handle plugin lifecycle

**Key Methods**:
- `load_plugins_from_directory()`: Load plugins from directory
- `register_plugin()`: Register a plugin instance
- `unregister_plugin()`: Remove a plugin

### McpManager

**Location**: `src/henchman/mcp/manager.py`  
**Role**: MCP (Model Context Protocol) server management

Manages connections to configured MCP servers and provides MCP tools. Discovery surfaces classify MCP as live only when both `mcp` and `mcp_auth` are registered in the current runtime.

**Responsibilities**:
- Connect to configured MCP servers
- Discover tools from MCP servers
- Handle MCP tool execution
- Manage MCP server lifecycle

**Key Methods**:
- `connect_all()`: Connect to all configured servers
- `disconnect_all()`: Disconnect from all servers
- `get_all_tools()`: Get all available MCP tools

### SessionManager

**Location**: `src/henchman/cli/session_manager.py`  
**Role**: Session management and persistence

Manages chat sessions including saving, loading, and resuming.

REPL and Textual turns save after their streams close, including cancellation.
`Agent.current_turn_messages` retains independent copies of the current turn's
messages before context compaction. Session synchronization replaces only that
turn's transcript, preserving earlier conversation, full tool results, tool-call
arguments, reasoning, and marked partial responses. The model's compacted working
context is separate from this persisted evidence.

Resuming a session restores the configured agent's system prompt and the selected
session's messages. Summaries from the previously active conversation are discarded.
Direct-role sessions restore to the selected specialist. These behaviors have
offline runtime coverage through save/load and a subsequent agent request;
interactive terminal rendering and live provider execution require separate checks.

**Responsibilities**:
- Save and load chat sessions
- Manage session templates
- Handle session auto-save
- Integrate with agent history

**Key Methods**:
- `set_session()`: Set current session
- `sync_agent_turn()`: Save the settled turn without losing evidence to compaction
- `save_session()`: Save session to disk
- `load_session()`: Load session from disk
- `list_templates()`: List available session templates

## Data Flow

### Interactive Session Flow

1. **Input Phase**:
   ```
   User → InputHandler.get_input() → REPL.process_input()
   ```

2. **Command Processing**:
   ```
   Slash command → CommandProcessor.handle_command() → OutputHandler → UIRenderer → User
   Regular input → REPL._run_agent() → ToolExecutor
   ```

3. **Agent Execution**:
   ```
   ToolExecutor.process_agent_stream() → 
     → ToolManager → Tool execution → 
     → Orchestrator → AgentPool → EventBus → 
     → OutputHandler → UIRenderer → User
   ```

4. **Plugin Integration**:
   ```
   PluginManager → Load plugins → Register tools/commands → 
     → ToolManager/CommandProcessor → Available to user
   ```

5. **MCP Integration**:
   ```
   McpManager → Connect to servers → Discover tools → 
     → ToolManager → Available as tools → Agent execution
   ```

6. **Session Management**:
   ```
   SessionManager → Save/load sessions → 
     → REPL session state → Agent history persistence
   ```

### Component Communication

Components communicate through well-defined interfaces:

1. **REPL to Components**: Direct method calls with dependency injection
2. **Components to REPL**: Callbacks and event handlers
3. **Component to Component**: Through shared references and interfaces
4. **Event-Based Communication**: `EventBus` for agent system events
5. **Plugin Hooks**: Extension points for plugin integration

## Design Principles

### SOLID Principles Applied

1. **Single Responsibility**: Each component has one clear purpose
2. **Open/Closed**: Components are open for extension, closed for modification
3. **Liskov Substitution**: Components can be replaced with compatible implementations
4. **Interface Segregation**: Components have focused, minimal interfaces
5. **Dependency Inversion**: Components depend on abstractions, not concretions

### Architectural Patterns

1. **Facade Pattern**: REPL provides simplified interface to complex subsystem
2. **Observer Pattern**: EventBus enables decoupled component communication
3. **Strategy Pattern**: Tool system allows different execution strategies
4. **Plugin Pattern**: Extensible architecture via plugin system
5. **Bridge Pattern**: UI abstraction separates rendering from logic

### Testing Strategy

- **Unit Tests**: Components are tested independently
- **Integration Tests**: Component coordination tested in `test_repl_integration.py`
- **End-to-End Tests**: Full workflow tests in `test_repl.py`
- **Plugin Tests**: Plugin system tests in `test_plugins.py`
- **MCP Tests**: MCP integration tests in `test_mcp.py`

### Performance Considerations

- **Async-First**: All I/O operations are asynchronous
- **Lazy Initialization**: Components initialized on-demand
- **Caching**: Frequent operations cached where appropriate
- **Streaming**: Event streaming for real-time feedback
- **Connection Pooling**: MCP connections managed efficiently
- **Background Processing**: RAG indexing and plugin loading in background

## Extension Points

### Adding New Components

1. Create component class in appropriate module
2. Implement focused interface
3. Update REPL initialization if needed
4. Add unit tests
5. Update integration tests

### Plugin Development

1. Create plugin class extending `Extension` base class
2. Implement `get_tools()` and/or `get_commands()` methods
3. Package as installable Python package
4. Register via entry points or directory placement

### MCP Server Integration

1. Configure MCP server in `settings.yaml`
2. Server tools automatically discovered and registered
3. Tools available to agents via tool registry
4. Trusted servers can auto-approve tool execution

### Customizing Existing Components

1. Subclass component
2. Override specific methods
3. Pass custom instance to REPL constructor
4. Maintain backward compatibility
5. Update configuration as needed

## Migration and Compatibility

### Backward Compatibility

Compatibility adapters preserve documented public imports and legacy attributes where covered by the test suite:

1. **Public API unchanged**: All existing methods preserved
2. **Attribute access**: Legacy attributes (`repl.agent`, `repl.tool_registry`) maintained
3. **Test compatibility**: Compatibility behavior is covered by focused tests
4. **External dependencies**: No breaking changes to external interfaces
5. **Configuration files**: Existing settings files continue to work

### Future Evolution

The [standards adoption RFC](standards.md) records the researched MCP, A2A,
OpenTelemetry, and tool-schema boundaries, implementation gaps, and phased
acceptance criteria. These protocol adoption phases remain future work.

The component architecture enables future enhancements:

1. **Enhanced Plugin System**: More extension points and lifecycle hooks
2. **Advanced MCP Support**: More protocol features and server types
3. **Distributed Architecture**: Multi-process or multi-machine deployment
4. **Advanced Caching**: Intelligent caching of LLM responses and tool results
5. **Metrics and Monitoring**: Comprehensive performance tracking
6. **UI Framework**: Alternative UI frameworks (TUI, Web, Desktop)

## System Evolution

### From Simple CLI to a Layered Agent Runtime

The architecture grew through earlier phase-based milestones, but a historical phase label is not a runtime availability guarantee. Current shipped foundations include the provider abstraction, core agent loop, local tool registry, configuration, terminal interfaces, sessions, multi-agent orchestration, configured MCP connectivity, and local extensions.

Remote infrastructure and registry-backed acquisition remain roadmap work. Integration scaffolds do not launch their target runtimes, recurring schedules are persisted without an executor, and generic help intentionally omits TUI-only dialogs. See `FEATURE_TODO.md` for the tier-by-tier roadmap and the shared discovery capability matrix for user-facing runtime classifications.

### Current Architecture Benefits

1. **Modularity**: Components can be developed and tested independently
2. **Extensibility**: Plugin and MCP systems enable easy extension
3. **Maintainability**: Clear separation of concerns reduces complexity
4. **Testability**: Well-defined interfaces enable comprehensive testing
5. **Scalability**: Architecture supports adding new components and features
6. **User Experience**: Rich UI and responsive interaction

## References

- [Multi-Agent Dev Team](agents.md) - Details on the agent orchestration layer
- [Tool System](tools.md) - Information about the tool registry and execution
- [Configuration Guide](configuration.md) - How to configure component behavior
- [API Reference](api.md) - Detailed API documentation for each component
- [MCP Integration](mcp.md) - Model Context Protocol server integration
- [Extensions Guide](extensions.md) - Plugin system and extension development
