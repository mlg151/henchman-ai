# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T17:15:00Z
## Bug Summary
The `update_problem` method silently fails when attempting to update a non-existent problem. Instead of raising an error or returning a failure indicator, it does nothing, which can mask bugs in calling code.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `update_problem` is called with a problem that doesn't exist, it should raise `ValueError` or return `False` | The method silently does nothing, making it impossible for callers to detect when they're trying to update a non-existent problem |
| Callers should be able to distinguish between successful update and failure | Callers cannot distinguish success from failure, potentially masking bugs |

## Root Cause
The `update_problem` method (lines 229-240) iterates through `self.problems_encountered` looking for a matching problem. If no match is found, the loop completes without finding a match, and the method returns `None` without indicating failure.

```python
def update_problem(self: WorkingMemory, updated: ProblemEntry) -> None:
    # ... validation ...
    for e in self.problems_encountered:
        if e.problem == updated.problem:
            e.status = updated.status
            e.resolution = updated.resolution
            break
    # No return statement or error if not found
```

## Fix Plan
1. Modify `update_problem` to raise `ValueError` when the problem to update is not found
2. Update the test `test_memory_update_problem_not_found` to expect `ValueError` instead of silent failure
3. Ensure all existing tests still pass after the change

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `update_problem` method to raise `ValueError` when problem not found (added `else` clause to the for loop)
2. `tests/agents/test_working_memory.py` - Updated `test_memory_update_problem_not_found` to expect `ValueError` instead of silent failure

## Changes Made
### 1. Source Code Fix (`src/henchman/agents/working_memory.py`)
- Added `else` clause to the for loop in `update_problem` method
- Raises `ValueError(f"Problem '{updated.problem}' not found")` when no matching problem is found
- Updated docstring to document the new `ValueError` exception

### 2. Test Update (`tests/agents/test_working_memory.py`)
- Updated `test_memory_update_problem_not_found` test
- Changed from expecting silent failure to expecting `ValueError`
- Updated test docstring to reflect new expected behavior
- Used `pytest.raises(ValueError, match="Problem 'Non-existent problem' not found")` context manager

## Verification
- All 50 tests in `tests/agents/test_working_memory.py` pass
- The fix follows TDD principles: wrote failing test first, then implemented fix
- The change is minimal and surgical, addressing only the identified bug
- No other functionality was affected