# FOUR LENSES OF FAILURE: CRITICAL BUG ANALYSIS
## Henchman-AI Delegation System Error Handling Bug

**Date**: 2024-03-05  
**Analyst**: The Bug Whisperer (Principal Software Engineer)  
**System**: `src/henchman/agents/delegation.py`  
**Component**: `run_delegation` method error handling  
**Priority**: CRITICAL - Silent Data Loss Bug

---

## EXECUTIVE SUMMARY

Identified a **critical error handling bug** in the delegation system where `DelegationExecutionError` exceptions are **double-wrapped**, causing **silent loss of error context**. This violates the principle of least surprise and makes debugging delegation failures extremely difficult.

### Key Findings:
1. **CRITICAL BUG**: `DelegationExecutionError` caught as generic `Exception`, losing error context
2. **SILENT FAILURE**: Original error details replaced with generic error message
3. **DESIGN INCONSISTENCY**: Error handling pattern inconsistent across delegation phases
4. **DEBUGGING IMPACT**: Makes delegation failures opaque and hard to diagnose

### Impact:
- **Severity**: HIGH - Silent data corruption (error context loss)
- **Likelihood**: HIGH - Every delegation execution error triggers this bug
- **Risk**: Debugging nightmares, incorrect error reporting, user confusion

---

## PHASE 1: INTENT VS. REALITY CHECK

### Original Bug Analysis

| Expected Behavior | Observed Risk | Root Cause |
|------------------|---------------|------------|
| `DelegationExecutionError` should propagate with original context | Error context lost in generic catch | **Design Flaw** |
| Error messages should preserve original exception details | Generic message replaces specific details | **Silent Data Loss** |
| Consistent error handling across all delegation phases | `DelegationExecutionError` treated differently | **Inconsistent Design** |

### Type Safety & Logic Gaps

**Bug Location**: `run_delegation` method, lines 571-580

```python
# BUGGY CODE (current):
except Exception as e:
    # Handle ALL execution errors consistently with other phases
    error_msg = (
        f"Failed to execute delegation for '{params.target_role}': {type(e).__name__}: {e}"
    )
    yield AgentEvent(
        type=EventType.ERROR,
        data=error_msg,
        source_agent="orchestrator",
    )
    return
```

**Problem**: This catches `DelegationExecutionError` (which already contains rich context) and replaces it with a generic message.

**Correct Behavior**: `DelegationExecutionError` should be caught separately and its original message preserved.

---

## PHASE 2: STATE & SIDE EFFECTS (THE ENTROPY AUDIT)

### State Mutation Analysis

**Shared State Risk**: The bug doesn't directly mutate shared state, but causes **information loss** in error reporting, which is a form of **state corruption**.

**Side Effects**: 
- Error context lost → debugging becomes guesswork
- Inconsistent error messages → user confusion
- Violates error handling contract established by exception hierarchy

### Scope Creep
The `run_delegation` method is doing too much error handling itself instead of delegating to specialized error handlers.

---

## PHASE 3: PERFORMANCE & RESOURCE MANAGEMENT

### Algorithmic Efficiency
**Bug Impact**: Not a performance issue, but a **correctness issue**.

**Memory Impact**: Error objects are created and immediately discarded (wasted allocations).

**I/O Impact**: Users waste time trying to debug with incomplete error information.

---

## PHASE 4: THE FORENSIC REFACTOR

### The "Clean" Version

```python
# FIXED CODE:
except DelegationExecutionError as e:
    # Preserve the original DelegationExecutionError context
    yield AgentEvent(
        type=EventType.ERROR,
        data=f"Failed to execute delegation for '{params.target_role}': {e.message}",
        source_agent="orchestrator",
    )
    return
except Exception as e:
    # Handle all other unexpected exceptions
    error_msg = (
        f"Unexpected error executing delegation for '{params.target_role}': {type(e).__name__}: {e}"
    )
    yield AgentEvent(
        type=EventType.ERROR,
        data=error_msg,
        source_agent="orchestrator",
    )
    return
```

### The "Unit of Doom" Test

```python
"""Unit test to trigger and verify the DelegationExecutionError double-wrapping bug."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from henchman.agents.delegation import (
    DelegationRunner,
    DelegationExecutionError,
    DelegationPreparationError,
)
from henchman.core.events import AgentEvent, EventType
from henchman.agents.orchestrator import DelegationParams


@pytest.mark.asyncio
async def test_delegation_execution_error_preserves_context():
    """Test that DelegationExecutionError preserves its original context."""
    
    # Mock dependencies
    mock_pool = MagicMock()
    mock_pool.get_agent.return_value = MagicMock(
        messages=[],
        clear_history=MagicMock(),
    )
    
    mock_settings = MagicMock()
    mock_settings.agents.max_delegation_depth = 3
    mock_settings.agents.max_delegation_turns = 10
    
    mock_ledger = MagicMock()
    mock_ledger.delegations = []
    mock_ledger.goal = None
    
    # Create delegation runner with mocked _run_agent_loop that raises DelegationExecutionError
    runner = DelegationRunner(
        pool=mock_pool,
        settings=mock_settings,
        shared_context=[],
        metrics=MagicMock(),
        run_agent_loop=AsyncMock(side_effect=DelegationExecutionError(
            "engineer",
            "Connection failed: timeout after 30 seconds"
        )),
        assess_completion=MagicMock(return_value=MagicMock(value="DONE"))
    )
    runner.ledger = mock_ledger
    
    # Create delegation params
    params = DelegationParams(
        target_role="engineer",
        task="Fix critical bug",
        brief={
            "done_when": "Tests pass",
            "context": "Test context",
            "files": ["src/file.py"],
            "background": "",
            "requirements": "",
            "depends_on": ""
        }
    )
    
    # Collect events
    events = []
    async for event in runner.run_delegation(params):
        events.append(event)
    
    # Find ERROR event
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert len(error_events) == 1, f"Expected 1 ERROR event, got {len(error_events)}"
    
    error_event = error_events[0]
    error_data = error_event.data
    
    # CRITICAL ASSERTION: Error message must contain the original context
    # Original bug: Would show "RuntimeError: Connection failed: timeout after 30 seconds"
    # Fixed version: Should show "Failed to execute delegation for 'engineer': Connection failed: timeout after 30 seconds"
    assert "Connection failed: timeout after 30 seconds" in error_data, \
        f"Error message lost original context: {error_data}"
    
    # Verify the error message format
    assert error_data.startswith("Failed to execute delegation for 'engineer':"), \
        f"Error message has wrong format: {error_data}"
    
    # Verify no double-wrapping (should not contain "RuntimeError:" or "DelegationExecutionError:")
    assert "RuntimeError:" not in error_data, f"Error was double-wrapped: {error_data}"
    assert "DelegationExecutionError:" not in error_data, f"Error was double-wrapped: {error_data}"


@pytest.mark.asyncio
async def test_generic_exception_still_handled():
    """Test that generic exceptions are still properly handled."""
    
    # Mock dependencies
    mock_pool = MagicMock()
    mock_pool.get_agent.return_value = MagicMock(
        messages=[],
        clear_history=MagicMock(),
    )
    
    mock_settings = MagicMock()
    mock_settings.agents.max_delegation_depth = 3
    mock_settings.agents.max_delegation_turns = 10
    
    mock_ledger = MagicMock()
    mock_ledger.delegations = []
    mock_ledger.goal = None
    
    # Create delegation runner with mocked _run_agent_loop that raises generic exception
    runner = DelegationRunner(
        pool=mock_pool,
        settings=mock_settings,
        shared_context=[],
        metrics=MagicMock(),
        run_agent_loop=AsyncMock(side_effect=ConnectionError("Network unreachable")),
        assess_completion=MagicMock(return_value=MagicMock(value="DONE"))
    )
    runner.ledger = mock_ledger
    
    # Create delegation params
    params = DelegationParams(
        target_role="engineer",
        task="Fix critical bug",
        brief={
            "done_when": "Tests pass",
            "context": "Test context",
            "files": ["src/file.py"],
            "background": "",
            "requirements": "",
            "depends_on": ""
        }
    )
    
    # Collect events
    events = []
    async for event in runner.run_delegation(params):
        events.append(event)
    
    # Find ERROR event
    error_events = [e for e in events if e.type == EventType.ERROR]
    assert len(error_events) == 1, f"Expected 1 ERROR event, got {len(error_events)}"
    
    error_event = error_events[0]
    error_data = error_event.data
    
    # Generic exceptions should show type and message
    assert "ConnectionError" in error_data, \
        f"Generic exception type not preserved: {error_data}"
    assert "Network unreachable" in error_data, \
        f"Generic exception message not preserved: {error_data}"
```

### Implementation Plan

1. **Fix the bug** in `run_delegation` method:
   - Add specific `except DelegationExecutionError` clause
   - Preserve original error message
   - Keep generic `except Exception` for other errors

2. **Update documentation**:
   - Fix incorrect comment about `RuntimeError` conversion
   - Document error handling contract

3. **Add unit tests**:
   - Test `DelegationExecutionError` context preservation
   - Test generic exception handling
   - Verify no double-wrapping occurs

4. **Run validation**:
   - Ensure all existing tests pass
   - Verify error messages are clear and helpful

### Risk Assessment

**Fix Risk**: LOW - Simple, targeted change
**Regression Risk**: LOW - Only affects error message formatting
**Benefit**: HIGH - Dramatically improves debugging experience

### Success Criteria

1. ✅ `DelegationExecutionError` messages preserved verbatim
2. ✅ No double-wrapping of error types
3. ✅ Generic exceptions still properly handled
4. ✅ All existing tests pass
5. ✅ Error messages are clear and actionable

---

## CONCLUSION

This critical bug represents a **silent failure** in the delegation system's error handling. By double-wrapping `DelegationExecutionError`, the system loses crucial debugging information, making it difficult to diagnose and fix delegation failures.

The fix is simple but impactful: treat `DelegationExecutionError` as a first-class citizen in the error handling flow, preserving its rich context for developers and users alike.