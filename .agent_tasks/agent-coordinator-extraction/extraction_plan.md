# Step-by-Step Extraction Plan

## Phase 1: Preparation (Day 1)
1. **Create test file** (`tests/cli/test_agent_coordinator.py`)
   - Import necessary modules
   - Create test class structure
   - Write initial setup/teardown

2. **Analyze dependencies** for each method
   - Map all instance variables used
   - Identify external dependencies
   - Document method signatures

## Phase 2: Extract `execute_tool_calls` (Day 1)
1. **Create AgentCoordinator skeleton**
   ```python
   class AgentCoordinator:
       def __init__(self, orchestrator, agent, tool_registry, session_manager, renderer, config):
           ...
   ```

2. **Copy `_execute_tool_calls` method**
   - Copy method body from REPL
   - Update `self.` references to instance variables
   - Fix imports

3. **Write tests** for `execute_tool_calls`
   - Mock tool registry
   - Test successful execution
   - Test error handling
   - Test confirmation flow

4. **Verify** method works in isolation

## Phase 3: Extract `process_agent_stream` (Day 2)
1. **Copy method** from REPL
2. **Update dependencies**:
   - Use `self.execute_tool_calls` instead of `self._execute_tool_calls`
   - Pass required instance variables
3. **Write comprehensive tests**:
   - Test event stream processing
   - Test tool call collection
   - Test content collection
   - Test error scenarios

## Phase 4: Extract `run_agent` and `run_agent_direct` (Day 2)
1. **Copy both methods**
2. **Handle monitor management**:
   - Create monitor instance in coordinator
   - Manage monitor lifecycle
3. **Update status handling**:
   - Pass status message as parameter
   - Remove callback dependency
4. **Write integration tests**

## Phase 5: Extract Deprecated Methods (Day 3)
1. **Copy `_handle_agent_event`** and `_handle_tool_call`
2. **Mark as deprecated** with `@deprecated` decorator
3. **Write minimal tests** for compatibility

## Phase 6: Integrate with REPL (Day 3)
1. **Update REPL constructor**:
   ```python
   self.agent_coordinator = AgentCoordinator(
       orchestrator=self.orchestrator,
       agent=self.agent,
       tool_registry=self.tool_registry,
       session_manager=self.session_manager,
       renderer=self.renderer,
       config=self.config,
   )
   ```

2. **Update method calls** in REPL:
   - Replace `self._run_agent()` with `self.agent_coordinator.run_agent()`
   - Replace `self._run_agent_direct()` with `self.agent_coordinator.run_agent_direct()`
   - Replace `self._process_agent_stream()` with `self.agent_coordinator.process_agent_stream()`
   - Replace `self._execute_tool_calls()` with `self.agent_coordinator.execute_tool_calls()`

3. **Remove extracted methods** from REPL

## Phase 7: Testing and Validation (Day 4)
1. **Run all tests** after each change
2. **Fix any broken tests**
3. **Verify line count reduction** (target: 200+ lines)
4. **Run full test suite** including e2e and smoke tests
5. **Check code quality** (ruff, mypy, coverage)

## Daily Checkpoints
- **EOD Day 1**: AgentCoordinator skeleton + `execute_tool_calls` extracted
- **EOD Day 2**: `process_agent_stream`, `run_agent`, `run_agent_direct` extracted
- **EOD Day 3**: Integration complete, all tests passing
- **EOD Day 4**: Final validation, documentation updated

## Risk Mitigation
- **Commit after each successful extraction**
- **Keep backup of original REPL file**
- **Test frequently** (after each method extraction)
- **Use feature branch** for safety

## Success Criteria
- [ ] All tests pass
- [ ] 100% test coverage for AgentCoordinator
- [ ] REPL line count < 596
- [ ] No breaking changes
- [ ] Code follows established patterns