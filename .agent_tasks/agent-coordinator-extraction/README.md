# Agent Coordinator Extraction

## Objective
Extract agent coordination logic from REPL class into a new AgentCoordinator class. The coordinator should handle:
1. orchestrator interaction
2. tool call collection and execution
3. event stream processing
4. monitoring and interruption handling

## Requirements
- Maintain all existing functionality
- Ensure 100% test coverage
- No breaking API changes
- Follow existing patterns from previous extractions (ToolManager, UIRenderer, ReplSessionManager)

## Exit Conditions
1. New AgentCoordinator class created in src/henchman/cli/agent_coordinator.py
2. REPL class updated to use it
3. All tests pass with 100% coverage
4. REPL line count reduced by at least 200 lines

## Current Status
- Initial analysis in progress
- REPL class is 796 lines
- Need to extract: `_process_agent_stream`, `_run_agent`, `_run_agent_direct`, `_execute_tool_calls`, and related methods

## Files to Modify
- src/henchman/cli/repl.py
- src/henchman/cli/agent_coordinator.py (new)
- tests/cli/test_repl.py (update tests)
- tests/cli/test_agent_coordinator.py (new tests)

## Analysis
The REPL class currently contains agent coordination logic that needs to be extracted:
1. `_process_agent_stream` (lines ~300-450): Main event stream processing
2. `_run_agent` (lines ~250-300): Main agent execution with monitoring
3. `_run_agent_direct` (lines ~300-350): Direct agent execution
4. `_execute_tool_calls` (lines ~450-550): Tool call batch execution
5. Related methods: `_show_turn_status`, `_handle_agent_event` (deprecated), `_handle_tool_call` (deprecated)

These methods handle orchestrator interaction, tool call collection/execution, event stream processing, and monitoring/interruption handling.