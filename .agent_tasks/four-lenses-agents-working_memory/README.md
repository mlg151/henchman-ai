# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-15T05:15:00+00:00
## Bug Summary
Invalid line number validation in `should_read_file` method happens AFTER early return for "full" file reads, causing invalid input (e.g., start=0) to be silently accepted when file was read fully.

## Lens
Phase 1: The Intent vs. Reality Check - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Invalid line numbers (start < 1 or end < 1) should always be reported as errors, regardless of whether file was previously read. | When file was read fully and invalid line numbers are provided (e.g., start=0), method returns False ("File already read (full)") instead of reporting invalid line number error. |
| Input validation should happen before business logic. | Input validation happens after checking if file was read fully, allowing invalid input to bypass validation. |

## Root Cause
In `should_read_file` method (lines 353-498), the validation for invalid line numbers (lines 399-403) occurs AFTER the early return for "full" file reads (lines 387-392). When a file was marked as "full" in working memory and the user requests to read with invalid line numbers (e.g., start=0, end=-1), the method returns early with "File already read (full)" before reaching the validation code that would report "Invalid line number: start must be positive (1-indexed), got start=0".

## Fix Plan
Move line number validation (lines 399-403 and 415-417) to immediately after parameter normalization (line 378), before any logic checking file read status. This ensures invalid input is always caught and reported, maintaining consistent error handling regardless of file read history.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Moved line number validation to happen before early return for "full" file reads (lines 379-387). Also fixed inconsistent error message when `valid_ranges` is empty (lines 482-484).
2. `tests/agents/test_working_memory.py` - Added test `test_memory_should_read_file_invalid_line_numbers_with_full_read` to verify the fix and fixed a bug in the test itself (removed incorrect assertion at line 807).

## Summary
The bug was that invalid line number validation (`start < 1`, `end < 1`, `start > end`) happened AFTER the early return for "full" file reads. When a file was marked as "full" in working memory and the user requested to read with invalid line numbers (e.g., `start=0`), the method would return `False, "File already read (full)"` instead of reporting the invalid line number error. The fix moves all input validation to the beginning of the `should_read_file` method, ensuring invalid input is always caught and reported consistently.