# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T04:15:00Z
## Bug Summary
The `update_problem` method lacks input validation, unlike `add_problem` which validates its input. This inconsistency can lead to `AttributeError` when `None` is passed, or unexpected behavior when wrong object types are passed.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Both `add_problem` and `update_problem` should validate input type for consistency | `add_problem` validates with `isinstance(entry, ProblemEntry)` but `update_problem` doesn't |
| Passing `None` to `update_problem` should raise a clear `TypeError` | Passing `None` causes `AttributeError: 'NoneType' object has no attribute 'problem'` |
| Passing wrong object type should be rejected | Duck-typing allows objects with same attributes to work, breaking type safety |

## Root Cause
The `add_problem` method has proper validation:
```python
if not isinstance(entry, ProblemEntry):
    raise TypeError(f"entry must be a ProblemEntry, got {type(entry).__name__}")
```

But `update_problem` lacks this validation:
```python
def update_problem(self: WorkingMemory, updated: ProblemEntry) -> None:
    for e in self.problems_encountered:
        if e.problem == updated.problem:  # <- crashes if updated is None
            e.status = updated.status
            e.resolution = updated.resolution
            break
```

This is a consistency bug and violates the principle of defensive programming. The type hint `ProblemEntry` is not enforced at runtime.

## Fix Plan
Add the same validation check to `update_problem` that exists in `add_problem`:
```python
if not isinstance(updated, ProblemEntry):
    raise TypeError(f"updated must be a ProblemEntry, got {type(updated).__name__}")
```

This ensures consistent error handling and prevents runtime `AttributeError` crashes.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Added input validation to `update_problem` method
2. `tests/agents/test_working_memory.py` - Added test `test_memory_update_problem_invalid_input` to verify the fix

## Verification
- Test `test_memory_update_problem_invalid_input` now passes (previously failed with `AttributeError`)
- All 48 tests in `test_working_memory.py` pass
- Full test suite (5694 tests) passes without regressions
- The fix ensures consistency between `add_problem` and `update_problem` methods