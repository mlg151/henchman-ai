# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T22:30:00Z
## Bug Summary
The `add_recent_file` method modifies the input `WorkingMemoryEntry` object in place by normalizing its `path` attribute, causing unexpected side effects for callers who might reuse the object.

## Lens
**Phase 2: State & Side Effects (The Entropy Audit)** - The code accidentally mutates inputs

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `add_recent_file` should not modify the input `WorkingMemoryEntry` object | `entry.path = _normalize_path(entry.path)` modifies the caller's object |
| Methods should be side-effect free with respect to their inputs | Caller's object is changed after method call, which could break caller's logic |
| If path normalization is needed, create a copy or new object | Original object is mutated, violating principle of least surprise |

## Root Cause
In `add_recent_file` (line 169), the code directly modifies the input object: `entry.path = _normalize_path(entry.path)`. This is done to ensure normalized paths are stored, but it has the side effect of changing the caller's object. The method should create a new `WorkingMemoryEntry` with the normalized path instead.

## Fix Plan
Replace the in-place modification with creation of a new `WorkingMemoryEntry` object using `dataclasses.replace()` or by constructing a new object with all attributes copied and the path normalized.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Added import of `replace` from `dataclasses`
   - Modified `add_recent_file` method to use `replace(entry, path=_normalize_path(entry.path))` instead of modifying `entry.path` in place
   
2. `tests/agents/test_working_memory.py`:
   - Added new test `test_memory_add_file_does_not_modify_input` to verify the fix
   - Test confirms input object is not modified and stored entry has normalized path

## Verification
- All existing tests pass (54 tests)
- New test passes, confirming the bug is fixed
- Custom verification script confirms input object is no longer modified
- The stored entry now has normalized path while input object remains unchanged