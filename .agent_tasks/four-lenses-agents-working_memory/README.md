# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T02:00:00Z
## Bug Summary
The `should_read_file` method incorrectly handles case-insensitive "full" values and whitespace in the `lines_read` field, causing files marked as fully read (e.g., "FULL", "Full", " full ") to be re-read unnecessarily.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Files marked as "full" (case-insensitive, with whitespace) should be considered fully read and return `False` for any line range | Files with "FULL", "Full", " full " etc. return `True` and get re-read, wasting context window and API calls |
| The method should normalize and compare `lines_read.strip().lower() == "full"` | Current code does exact string match: `match.lines_read.strip().lower() == "full"` but only checks once, missing case variations |
| Line range parsing should handle edge cases consistently | Inconsistent handling leads to different behavior for same semantic meaning |

## Root Cause
The bug is in the `should_read_file` method at line 238. The code checks `if match.lines_read.strip().lower() == "full":` but this check is only performed when `match` is found. However, the real issue is that when `LineRange.from_str(match.lines_read)` is called with "FULL" or "Full", it returns `None` (because "FULL" doesn't match "start-end" format), and the method falls through to return `True` with reason "Cannot determine overlap - invalid lines_read format".

Additionally, the test suite reveals multiple related issues:
1. Case-insensitive "full" not handled
2. Whitespace around "full" not properly normalized
3. Multiple entries for same file - should use most recent entry, not first found

## Fix Plan
1. Fix the `should_read_file` method to properly handle case-insensitive "full" values by checking `match.lines_read.strip().lower() == "full"` before attempting to parse as a line range.
2. Ensure the check happens in the right place in the logic flow (before attempting `LineRange.from_str`).
3. Add proper normalization for whitespace and case variations.
4. The fix should be minimal and surgical - only change what's necessary to fix the bug.

## Status: IN PROGRESS