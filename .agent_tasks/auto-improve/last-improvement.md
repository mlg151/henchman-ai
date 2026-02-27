# Improvement Summary

**Date/Time**: 2026-02-27T16:40:00Z (XP Refactoring Agent)

**Files Changed**:
1. `src/henchman/core/agent.py` - Refactored finish reason handling to eliminate duplicate logic between STOP and other finish reasons.

**Identified Smells Addressed**:
- **Duplicate Code (🟠 HIGH)**: `Function '_handle_stop_finish' is an exact duplicate of '_handle_other_finish' at core/agent.py:618`.

**Refactoring Strategy Applied**:
1. **Extract Method**: Introduced a generic `_yield_remaining_content(state)` method to encapsulate the logic of yielding content that was accumulated but not yet emitted during streaming.
2. **Once and Only Once (DRY)**: Replaced specific calls to `_handle_stop_finish` and `_handle_other_finish` in `_handle_finish_reason` with the new generic method.
3. **Remove Redundancy**: Deleted the redundant `_handle_stop_finish` and `_handle_other_finish` methods.

**Refactored Code (Pattern)**:
```python
    # In _handle_finish_reason:
    if finish_reason in (FinishReason.STOP, FinishReason.LENGTH, FinishReason.CONTENT_FILTER):
        async for event in self._yield_remaining_content(state):
            yield event
```

**Testing Implications**:
- **Baseline Verified**: Ran `tests/core/test_agent.py` before and after changes.
- **All Tests Pass**: 27 tests in `tests/core/test_agent.py` passed with 74% coverage.
- **Behavioral Consistency**: The logic for yielding remaining content remains exactly the same for all relevant finish reasons, ensuring no regressions in streaming or non-streaming output.

**Code Quality Improvements**:
- ✅ **DRY Compliance**: Eliminated exact code duplication across two methods.
- ✅ **Intention-Revealing Code**: `_yield_remaining_content` better describes the actual action being performed at the end of a stream.
- ✅ **Simplicity**: Simplified the dispatch logic in `_handle_finish_reason`.
