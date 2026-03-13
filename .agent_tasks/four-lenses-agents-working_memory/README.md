# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-13T23:15:00Z
## Bug Summary
The `should_read_file` method doesn't validate line number inputs before creating a `LineRange` object, causing `ValueError` exceptions to propagate when invalid line numbers (e.g., 0 or negative) are provided.

## Lens
Phase 1: The Intent vs. Reality Check - Type Safety

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `should_read_file` is called with invalid line numbers (e.g., start=0, end=10), it should return a tuple with `True` and an appropriate error message, not raise an unhandled exception. | The method creates a `LineRange(start, end)` without validating inputs first. `LineRange.__post_init__` validates that line numbers are positive (1-indexed) and raises `ValueError` if not. This exception propagates to the caller, breaking the method's contract of returning a tuple. |

## Root Cause
The `should_read_file` method assumes `start` and `end` parameters are valid line numbers (≥1). It checks `if start > end:` on line 268 but doesn't check for non-positive values. When it creates `LineRange(start, end)` on line 271, the `LineRange.__post_init__` validation raises `ValueError` for invalid inputs.

This violates the method's interface contract: it should always return a `tuple[bool, str]`, not raise exceptions for invalid input. The method already handles some invalid cases (e.g., `start > end`) by returning an error message, but misses the non-positive line number case.

## Fix Plan
Add validation in `should_read_file` to check `start >= 1 and end >= 1` before creating `LineRange`. If validation fails, return `(True, "Invalid line numbers: must be positive (1-indexed)")` (or similar message).

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Added validation for non-positive line numbers in `should_read_file` method (lines 270-273)
2. `tests/agents/test_working_memory.py` - Added test `test_memory_should_read_file_invalid_line_numbers` to verify the fix (lines 515-540)

## Verification
- The failing test was written first (TDD) and confirmed to fail with `ValueError`
- The fix was implemented by adding validation for `start < 1 or end < 1` before creating `LineRange`
- All existing tests continue to pass (44 tests in test_working_memory.py)
- All project tests pass (5690 tests total)