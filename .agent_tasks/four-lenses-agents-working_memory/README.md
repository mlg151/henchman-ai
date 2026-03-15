# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T14:00:00+00:00
## Bug Summary
The `should_read_file` method has a critical bug where it incorrectly handles files that were read fully (lines_read="full") when checking partial ranges (start=None or end=None). When a file was read fully and a partial range is requested (e.g., start=10, end=None), the method returns True with an error about invalid line numbers instead of returning False because the file was already read fully.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When a file was read fully (lines_read="full"), any subsequent read request (full or partial) should return False (skip) | When start=None or end=None is provided with a file that was read fully, the method validates line numbers AFTER checking for "full", causing it to return True with an error about invalid line numbers instead of returning False |
| Line number validation should happen BEFORE checking if file was read fully | Line number validation happens AFTER the early return for "full" files, causing incorrect behavior for invalid line numbers |
| Invalid line numbers (e.g., start=0) should always be reported as errors, even for files that were read fully | For files read fully, invalid line numbers are not validated, and the method returns False (skip) instead of True (read) with error |

## Root Cause
The bug is in the `should_read_file` method at lines 361-502. The method has this flow:
1. Normalize path
2. Find matching entries
3. Check if ANY entry has lines_read="full" (case-insensitive, whitespace-normalized)
4. If yes, return False immediately ("File already read (full)")
5. **BUG**: Line number validation (start < 1, end < 1, start > end) happens AFTER the "full" check
6. This means if a file was read fully and invalid line numbers are provided (e.g., start=0), the method returns False instead of reporting the invalid line number error

Additionally, when only start OR end is provided (not both) for a file that was read fully, the method doesn't handle this case correctly in the partial range logic.

## Fix Plan
1. Move line number validation to happen BEFORE checking if file was read fully
2. Ensure invalid line numbers are always reported as errors, regardless of file read status
3. Update the logic for partial ranges (start=None or end=None) to correctly handle files that were read fully
4. Add comprehensive test coverage for these edge cases

## Status: IN PROGRESS