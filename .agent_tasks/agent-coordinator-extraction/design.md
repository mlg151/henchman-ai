# AgentCoordinator Design

## Purpose
Extract agent coordination logic from REPL class into a new AgentCoordinator class that handles:
1. Orchestrator interaction
2. Tool call collection and execution
3. Event stream processing
4. Monitoring and interruption handling

## Methods to Extract
From REPL class:
1. `_process_agent_stream` (lines 458-627) - Main event stream processing
2. `_run_agent` (lines 362-415) - Main agent execution with monitoring
3. `_run_agent_direct` (lines 416-456) - Direct agent execution
4. `_execute_tool_calls` (lines 629-717) - Tool call batch execution
5. `_show_turn_status` (lines 720-731) - Display turn status
6. `_handle_agent_event` (lines 733-763) - DEPRECATED, keep for compatibility
7. `_handle_tool_call` (lines 765-792) - DEPRECATED, keep for compatibility

## Dependencies Analysis

### Required from REPL:
1. `self.orchestrator` - For `run()` and `run_direct()` methods
2. `self.agent` - For `turn`, `unlimited_mode`, `continue_with_tool_results()`, `submit_tool_result()`
3. `self.tool_registry` - For tool execution
4. `self.session_manager` - For recording messages and tool results
5. `self.renderer` - For UI output
6. `self.config` - For `base_tool_iterations`, `max_tool_calls_per_turn`
7. `self.current_monitor` - For monitoring interruption
8. `self._get_rich_status_message()` - For status updates

### External Dependencies:
1. `asyncio` - For async operations
2. `contextlib` - For suppress
3. `AsyncIterator` - Type hint
4. `AgentEvent`, `EventType` - Event handling
5. `ToolCall` - Tool call type
6. `Status` - Rich status object

## Interface Design

### AgentCoordinator Class:
```python
class AgentCoordinator:
    def __init__(
        self,
        orchestrator: Orchestrator,
        agent: Agent,  # tech_lead from orchestrator
        tool_registry: ToolRegistry,
        session_manager: ReplSessionManager,
        renderer: UIRenderer,
        config: ReplConfig,
        get_status_message: Callable[[], str]  # Callback for status
    ):
        ...
    
    async def run_agent(self, user_input: str) -> None:
        """Main agent execution with monitoring."""
    
    async def run_agent_direct(self, role: str, user_input: str) -> None:
        """Direct agent execution."""
    
    async def process_agent_stream(
        self,
        event_stream: AsyncIterator[AgentEvent],
        content_collector: list[str] | None = None,
        status_obj: Status | None = None,
    ) -> None:
        """Process agent event stream."""
    
    async def execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        content_collector: list[str] | None = None,
    ) -> None:
        """Execute batch of tool calls."""
    
    def show_turn_status(self) -> None:
        """Display turn status."""
    
    # Deprecated methods for compatibility
    async def handle_agent_event(...) -> None:
    async def handle_tool_call(...) -> None:
```

## Integration Plan
1. Create AgentCoordinator class with extracted methods
2. Update REPL to initialize AgentCoordinator
3. Update REPL methods to delegate to AgentCoordinator
4. Update tests to work with new structure
5. Ensure 100% test coverage
6. Verify line count reduction

## Challenges
1. Circular dependencies between REPL and AgentCoordinator for `_get_rich_status_message()`
2. `self.current_monitor` management
3. Maintaining backward compatibility for deprecated methods
4. Ensuring all tests pass

## Solution
1. Pass `get_status_message` as a callback to AgentCoordinator
2. AgentCoordinator should manage its own monitor instance
3. Keep deprecated methods in AgentCoordinator for compatibility
4. Create comprehensive tests for AgentCoordinator