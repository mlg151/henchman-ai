# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2024-03-14T20:15:00Z
## Bug Summary
The `should_read_file` method fails to validate line numbers when only one of `start` or `end` is provided (i.e., `start=10, end=None` or `start=None, end=50`). It returns `True` with message "File not fully read - partial read recorded" without checking if the provided line number is valid (positive, 1-indexed).

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `should_read_file` is called with `start=0, end=None` (invalid start line 0), it should return `True` with an error message about invalid line numbers (e.g., "Invalid line numbers: must be positive (1-indexed), got start=0"). | The method returns `True` with message "File not fully read - partial read recorded", which is misleading and doesn't indicate the actual problem (invalid line number). |
| When `should_read_file` is called with `start=-5, end=None` (negative start), it should return an error about invalid line numbers. | The method returns `True` with message "File not fully read - partial read recorded". |
| When `should_read_file` is called with `start=None, end=0` (invalid end line 0), it should return an error. | The method returns `True` with message "File not fully read - partial read recorded". |
| The method should validate `start` parameter when provided (not `None`) even if `end` is `None`. Similarly, it should validate `end` when provided even if `start` is `None`. | The method only validates line numbers when both `start` and `end` are provided. |

## Root Cause
The bug is in the `should_read_file` method at lines 267-280. The logic flow is:

1. Line 267: `if start is None or end is None: return True, "File not fully read - partial read recorded"`
2. Line 274: `if start > end: return True, f"Invalid line range: start ({start}) > end ({end}) - treating as new read"` (only if both not None)
3. Line 278: `if start < 1 or end < 1: return True, f"Invalid line numbers: must be positive (1-indexed), got start={start}, end={end}"` (only if both not None)

The validation at lines 274 and 278 only runs if both `start` and `end` are not `None`. But we should validate `start` if provided (even if `end` is `None`) and validate `end` if provided (even if `start` is `None`).

## Fix Plan
Modify the `should_read_file` method to:
1. Check if `start` is provided (not `None`) and validate it's positive (`start >= 1`)
2. Check if `end` is provided (not `None`) and validate it's positive (`end >= 1`)
3. If both are provided, also validate `start <= end`
4. Return appropriate error messages for invalid line numbers

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `should_read_file` method to validate line numbers when only one of `start` or `end` is provided (lines 267-280).
2. `tests/agents/test_working_memory.py` - Added new test `test_memory_should_read_file_invalid_line_numbers_partial_range` to verify the fix.

## Summary
The bug was that `should_read_file` method failed to validate line numbers when only one of `start` or `end` was provided (e.g., `start=10, end=None` or `start=None, end=50`). It would return `True` with message "File not fully read - partial read recorded" without checking if the provided line number was valid (positive, 1-indexed).

The fix adds validation for `start` if provided (even if `end` is `None`) and for `end` if provided (even if `start` is `None`). Now invalid line numbers like `start=0`, `start=-5`, `end=0`, etc. return appropriate error messages instead of the misleading "File not fully read" message.