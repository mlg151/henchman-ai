# Technical Guidance for AgentCoordinator Implementation

## From: Tech Lead
## To: Engineer
## Date: Current

## Implementation Strategy

### 1. **Start with Test-Driven Development**
- Create `tests/cli/test_agent_coordinator.py` FIRST
- Write tests for each method to be extracted
- Ensure 100% test coverage from the beginning

### 2. **Follow Established Patterns**
Look at existing extracted classes for patterns:
- `ToolManager`: Manages tool registry and confirmation
- `UIRenderer`: Handles UI output with renderer interface  
- `ReplSessionManager`: Manages session persistence

Patterns to follow:
- Dependency injection in constructor
- Clear public API methods
- Proper error handling
- Async/await patterns consistent with existing code

### 3. **Address Technical Considerations**

#### Circular Dependency Solution:
Instead of `get_status_message` callback, pass the status message directly:
```python
async def run_agent(self, user_input: str, status_message: str | None = None) -> None:
```

#### Monitor Management:
AgentCoordinator should create and manage its own monitor instance:
```python
from henchman.cli.input import KeyMonitor

monitor = KeyMonitor()
monitor_task = asyncio.create_task(monitor.monitor())
```

#### Error Propagation:
Ensure errors are properly caught and logged:
```python
try:
    await self.process_agent_stream(...)
except Exception as e:
    self.renderer.error(f"Agent coordination error: {e}")
    raise
```

### 4. **Implementation Order**
1. Create empty AgentCoordinator class with constructor
2. Extract `execute_tool_calls` method first (simplest)
3. Extract `process_agent_stream` method
4. Extract `run_agent` and `run_agent_direct` methods
5. Extract deprecated methods for compatibility
6. Update REPL to use AgentCoordinator
7. Run tests after each step

### 5. **Testing Strategy**
- Mock all dependencies (orchestrator, agent, tool_registry, etc.)
- Test each method in isolation
- Test error scenarios
- Test integration with REPL
- Ensure 100% coverage

### 6. **Quality Gates**
- All existing tests must pass
- No new linting errors
- Type checking must pass
- 100% test coverage for new code
- REPL line count reduced by at least 200 lines

### 7. **Risk Mitigation**
- Keep deprecated methods in AgentCoordinator for compatibility
- Use feature flag if needed (but prefer direct replacement)
- Commit frequently with descriptive messages
- Run full test suite after each significant change

## Success Metrics
1. REPL class reduced from 796 to < 596 lines
2. All tests pass (including e2e and smoke tests)
3. 100% test coverage for AgentCoordinator
4. No breaking changes to public API
5. Code follows established patterns and conventions

## Available for Questions
I'm available to review design decisions, code structure, and implementation approach. Let me know if you encounter any technical challenges.