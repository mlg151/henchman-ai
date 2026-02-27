# Infinite Loop Bug Fix — Missing Tool Execution in Orchestrator

## Bug
`auto-improve.sh` and `auto-doc-improve.sh` produce infinite loops where the agent
repeatedly generates the same tool call, gets "Message sequence repaired" warnings,
and never makes progress.

## Root Cause
In `src/henchman/agents/orchestrator.py`, the `_run_agent_loop` method was missing a
call to `_process_pending_tool_calls()`. The method existed (defined at line ~1444)
but was never invoked from the main loop.

### Broken flow
1. Agent generates response with `tool_calls` (e.g., `read_file`)
2. `_collect_events_and_tool_calls` yields `TOOL_CALL_REQUEST` events and collects tool calls
3. **Bug:** Loop skips directly to `agent.continue_with_tool_results()` without executing tools
4. `_prepare_for_streaming` finds broken messages → repairs by stripping `tool_calls`
5. Agent regenerates the same tool call → infinite loop

### Fixed flow
1–2. Same as above
3. **Fix:** `_process_pending_tool_calls()` executes each tool and calls `agent.submit_tool_result()`
4. `agent.continue_with_tool_results()` now has valid tool responses
5. Agent continues normally

## Fix
**File:** `src/henchman/agents/orchestrator.py`  
**Location:** `_run_agent_loop`, between `_enforce_turn_limits` and `agent.continue_with_tool_results()`

Added:
```python
# Execute all pending tool calls (regular + delegation)
async for event in self._process_pending_tool_calls(
    agent, pending_tool_calls, depth, tool_errors
):
    yield event

tool_call_count += len(pending_tool_calls)
```

## Testing
- 51 orchestrator tests pass
- 185 core/validation tests pass
- No regressions
