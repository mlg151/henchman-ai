# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T00:00:00Z
## Bug Summary
The `should_read_file` method raises `AttributeError` when `WorkingMemoryEntry.lines_read` is `None` (e.g., from deserialization of YAML with `lines_read: null`), instead of handling it gracefully.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps: The code assumes a "happy path" where `lines_read` is always a string, but it could be `None` after deserialization.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `should_read_file` should handle `lines_read=None` gracefully (return `True` with appropriate reason) | Method raises `AttributeError: 'NoneType' object has no attribute 'strip'` |
| Deserialization from YAML with missing or null `lines_read` should work | Crash when trying to use deserialized data |
| Core functionality should be robust to malformed data | Core method crashes on unexpected input |

## Root Cause
The `should_read_file` method calls `matches[0].lines_read.strip().lower()` without checking if `lines_read` is a string. When `WorkingMemoryEntry` is deserialized from YAML with `lines_read: null` or missing `lines_read` field, `lines_read` becomes `None`. The method then crashes when trying to call string methods on `None`.

## Fix Plan
1. Add a check in `should_read_file` to handle `lines_read` being `None` or not a string
2. Return `True` with appropriate error message (e.g., "Cannot determine - invalid lines_read format")
3. Consider adding validation in `WorkingMemoryEntry.from_dict` to ensure `lines_read` is a string

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Modified `should_read_file` method to check `isinstance(lines_read, str)` before calling `.strip().lower()`
   - Modified `LineRange.from_str` method to return `None` if input is not a string
2. `tests/agents/test_working_memory.py`:
   - Added `test_memory_should_read_file_lines_read_none` test to verify the fix

## Verification
- Added test demonstrates the bug (fails before fix, passes after fix)
- All existing tests continue to pass
- The fix handles edge case where `lines_read` is `None` (e.g., from YAML deserialization with `lines_read: null`)
- Method now returns `True` with appropriate error message instead of raising `AttributeError`