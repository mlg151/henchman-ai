# Interactive Session Functional Tests

This directory contains comprehensive functional tests for interactive sessions in Henchman-AI. These tests simulate realistic user workflows to shake out integration bugs.

## What These Tests Validate

### 1. Multiple Message Exchanges
- User and assistant conversation flow
- Context maintenance across turns
- Message role alternation (user/assistant)
- Session history accumulation

### 2. Tool Calls
- File operations (ls, read_file, write_file)
- Shell command execution
- Tool result handling
- Tool call recording in session
- Tool execution through UI

### 3. Skills Usage
- Skill learning from session patterns
- Skill storage interaction
- Skill execution framework
- Skill parameter handling

### 4. Planning Session
- Plan mode activation/deactivation via /plan command
- Tool restrictions in plan mode (read-only)
- Mode transitions (normal ↔ plan)
- System prompt injection for plan mode

### 5. Session Management
- Message persistence throughout workflow
- State maintenance across operations
- Session metadata (project hash, timestamps)
- Auto-save functionality

### 6. Integration Points
- REPL ↔ Agent communication
- REPL ↔ ToolRegistry connection
- REPL ↔ CommandRegistry routing
- REPL ↔ SessionManager persistence
- REPL ↔ OutputRenderer display

## Test Files

### 1. Comprehensive Tests
- test_comprehensive_interactive_session.py - Full workflow with all components
- test_runnable_interactive_session.py - Simplified, runnable version

### 2. Component Tests
- test_repl_e2e.py - End-to-end REPL flows
- test_tool_integration.py - Tool execution through UI
- test_slash_commands.py - Slash command integration
- test_plan_mode.py - Planning mode functionality
- test_skills.py - Skills system integration

## How to Run

### Using the Test Runner
```bash
# Run all tests
python run_interactive_tests.py

# Run quick test only
python run_interactive_tests.py --quick

# Run individual component tests
python run_interactive_tests.py --components

# Run using pytest
python run_interactive_tests.py --pytest
```

### Using Pytest Directly
```bash
# Run all interactive session tests
python -m pytest tests/ui_integration/test_runnable_interactive_session.py -v
python -m pytest tests/ui_integration/test_comprehensive_interactive_session.py -v

# Run specific test
python -m pytest tests/ui_integration/test_runnable_interactive_session.py::test_basic_interactive_session -v
```

### Running Individual Tests
```bash
# Direct execution
python tests/ui_integration/test_runnable_interactive_session.py
```

## Test Workflow Example

The comprehensive test simulates this workflow:

1. **Initial Setup**
   - User greets assistant
   - Assistant responds with greeting

2. **File Operations**
   - User asks to list files → ls tool call
   - User asks to read README → read_file tool call
   - User asks to run tests → shell tool call

3. **Skills Integration**
   - Assistant suggests saving workflow as skill
   - Skill learning process
   - Skill storage interaction

4. **Planning Session**
   - User enters plan mode via /plan command
   - Read-only operations in plan mode
   - User exits plan mode via /plan command

5. **Write Operations**
   - User creates test file → write_file tool call
   - Session completion

6. **Verification**
   - Session message count validation
   - Tool call count verification
   - State persistence checks

## Expected Output

Successful tests will show:
- Multiple message exchanges recorded
- Tool executions completed
- Skills system interactions
- Plan mode toggling
- Session persistence throughout

## Debugging Tips

If tests fail:

1. **Check Session State**
   ```python
   print(f"Messages: {len(repl.session.messages)}")
   print(f"Tool calls: {len([m for m in repl.session.messages if m.tool_calls])}")
   ```

2. **Check Provider Calls**
   ```python
   print(f"Provider calls: {provider.call_count}")
   ```

3. **Check Console Output**
   ```python
   output = console.export_text()
   print(f"Console output length: {len(output)}")
   ```

4. **Check Plan Mode State**
   ```python
   print(f"Plan mode: {repl.session.plan_mode}")
   ```

## Adding New Tests

When adding new interactive session tests:

1. **Follow the Pattern**
   - Use the InteractiveSessionProvider pattern for deterministic responses
   - Mock external dependencies (skill store, etc.)
   - Verify session state after each operation

2. **Test One Thing**
   - Each test should focus on one aspect of the workflow
   - Comprehensive tests should combine multiple aspects

3. **Verify Integration**
   - Check that components are properly connected
   - Verify data flows between components
   - Test error conditions and recovery

## CI Integration

These tests should be included in CI to catch integration bugs:
- Run on every PR
- Run before releases
- Monitor for regressions

## Coverage Goals

- 100% of slash commands have integration tests
- 100% of built-in tools have UI integration tests
- All component connections verified
- Realistic user workflows tested
