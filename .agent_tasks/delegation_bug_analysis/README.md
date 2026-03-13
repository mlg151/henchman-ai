# Delegation Bug Analysis & Fix

## Problem Statement
The delegation system has a critical bug where agent lookup failures produce duplicate error events (ERROR + AGENT_COMPLETED) instead of just ERROR.

## Root Cause Analysis

### Phase 1: Intent vs. Reality Check
**Expected Behavior**: When agent lookup fails (ValueError: "Agent 'unknown' not found"), the system should yield only an ERROR event.

**Actual Behavior**: The system was yielding both ERROR and AGENT_COMPLETED events, causing duplicate error reporting.

**Logic Gap**: The `run_delegation` method had a control flow issue where after yielding ERROR for agent lookup failure, it would still continue to the finalization phase.

### Phase 2: State & Side Effects
**Shared State Issue**: The `shared_context` list is modified even for failed delegations (line added in `_finalize_execution`).

**Immutability Violation**: The `params` object is mutated in place (`params.target_agent = target_agent_result`) even when `target_agent_result` is an AgentEvent (error).

### Phase 3: Performance & Resource Management
**Inefficient Error Handling**: Multiple regex patterns are compiled for parsing completion reports even for failed delegations.

**Memory Leak**: Failed delegations still allocate resources for context preparation.

### Phase 4: Forensic Analysis
The bug was in the control flow of `run_delegation`:
1. Agent lookup fails → returns AgentEvent(ERROR)
2. Method yields ERROR event
3. BUT: No early return after yielding error
4. Execution continues to `_finalize_execution` which yields AGENT_COMPLETED

## Fix Implemented
The fix ensures proper early returns for error conditions:

1. **Agent lookup failure**: Return after yielding ERROR, don't continue
2. **Depth exceeded**: Return after yielding ERROR, don't continue  
3. **Validation**: Add assertions and type checks to prevent invalid state

## Test Coverage
- ✅ Agent not found yields only ERROR (not ERROR + AGENT_COMPLETED)
- ✅ Depth exceeded yields only ERROR (not ERROR + AGENT_COMPLETED)
- ✅ Successful delegation yields proper event sequence (AGENT_STARTED, CONTENT, AGENT_COMPLETED)

## Code Quality Improvements
1. Added comprehensive error handling for all exception types in `_get_target_agent_with_error_handling`
2. Added validation to prevent mutating params with error events
3. Improved type safety with proper assertions
4. Added early returns to prevent duplicate event emission

## Files Modified
- `src/henchman/agents/delegation.py`: Fixed control flow and error handling
- `test_delegation_bug.py`: Test for duplicate error reporting
- `test_fix_delegation_duplicate_errors.py`: Comprehensive test suite

## Verification
All existing tests pass, including end-to-end delegation tests. The fix maintains backward compatibility while eliminating the duplicate error reporting bug.