# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T10:15:00Z
## Bug Summary
When `lines_read` is `None` (e.g., from YAML `null`), `should_read_file` returns `True` with misleading reason "File not fully read - partial read recorded" instead of accurate "Cannot determine - invalid lines_read format". This inconsistency causes confusion and hides the root cause of invalid data.

## Lens
Phase 1: The Intent vs. Reality Check (Logic Gaps)

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Invalid `lines_read` values (None, empty string, malformed) should consistently return "Cannot determine - invalid lines_read format" as the reason. | When `start=None and end=None` and `lines_read` is invalid, returns misleading "File not fully read - partial read recorded". |
| Error messages should accurately reflect the problem to aid debugging. | Misleading message hides the fact that `lines_read` is invalid (e.g., `None` from YAML corruption). |
| Consistent error handling for all invalid `lines_read` cases. | Inconsistent: partial range requests get correct error, full file requests get misleading error. |

## Root Cause
In `should_read_file`, when `start=None and end=None` (request to read entire file), the method checks if file was read "full" (lines 392-397). If not, it immediately returns `True, "File not fully read - partial read recorded"` (lines 410-412) without checking if `lines_read` is valid. This bypasses the `valid_ranges` check that would reveal invalid `lines_read` format.

For partial range requests (`start=X, end=None` or `start=None, end=Y`), the code correctly checks `if not valid_ranges: return True, "Cannot determine - invalid lines_read format"` (lines 416, 450).

## Fix Plan
1. Move the `valid_ranges` collection and validation BEFORE the early return at line 410.
2. Check `if not valid_ranges:` after collecting ranges but before deciding reason.
3. For invalid `lines_read`, return consistent error message "Cannot determine - invalid lines_read format" regardless of `start`/`end` values.
4. Maintain existing behavior for valid but non-full `lines_read` (still return `True` but with accurate reason).

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `should_read_file` method to check `valid_ranges` before returning "File not fully read - partial read recorded" when `start=None and end=None`. Now returns "Cannot determine - invalid lines_read format" for invalid `lines_read` values (None, empty string, malformed), consistent with partial range requests.

## Verification
- Added test cases demonstrating the bug (invalid `lines_read` with `start=None, end=None` returns misleading error)
- Fixed code now returns consistent error message "Cannot determine - invalid lines_read format"
- All existing tests pass (5711 tests)
- No regression in functionality