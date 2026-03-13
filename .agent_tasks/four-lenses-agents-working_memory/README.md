# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-13T20:00:00Z
## Bug Summary
The `should_read_file` method performs case-sensitive comparison `match.lines_read == "full"`, causing incorrect behavior when `lines_read` is "FULL", "Full", or any other case variation. Files marked as fully read with non-lowercase "full" are incorrectly treated as having invalid `lines_read` format, causing the system to think they need to be re-read.

## Lens
**Logic Gaps** - The code assumes a "happy path" where `lines_read` is always lowercase "full", but in reality, data could come from different sources (serialization, user input, etc.) with different casing.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When a file is marked as fully read (`lines_read` indicates full read regardless of case), any subsequent request to read any part of that file should return `False` (already read). | The code returns `True` with reason "Cannot determine overlap - invalid lines_read format" for case variations like "FULL", causing unnecessary file re-reads. |
| The system should be robust to case variations in `lines_read` values. | The system is fragile and fails on case variations. |

## Root Cause
1. Line 236 in `should_read_file`: `if match.lines_read == "full":` performs exact string match.
2. If `lines_read` is not exactly "full" (e.g., "FULL", "Full"), the check fails.
3. The code then tries to parse it as a line range via `LineRange.from_str(match.lines_read)`, which returns `None` for "FULL".
4. Finally, it returns `True, "Cannot determine overlap - invalid lines_read format"`.

## Fix Plan
Change the case-sensitive check `match.lines_read == "full"` to a case-insensitive check: `match.lines_read.lower() == "full"`.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Line 257: Changed `if match.lines_read == "full":` to `if match.lines_read.lower() == "full":`
2. `tests/agents/test_working_memory.py` - Added new test `test_memory_should_read_file_full_case_insensitive` to verify the fix and prevent regression.

## Test Results
- All 42 tests in `tests/agents/test_working_memory.py` pass
- The new test `test_memory_should_read_file_full_case_insensitive` passes, confirming the fix works for both uppercase "FULL" and mixed case "Full"
- Coverage improved: `src/henchman/agents/working_memory.py` now has 97% coverage (only 4 uncovered branches remain in other methods)