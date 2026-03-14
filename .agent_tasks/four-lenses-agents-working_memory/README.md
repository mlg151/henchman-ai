# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T19:00:00Z
## Bug Summary
The `should_read_file` method has a critical bug where it incorrectly returns `False` (skip reading) when a file was fully read in the past but partially read more recently. It checks if ANY entry has `lines_read == "full"`, instead of checking if the MOST RECENT entry has `lines_read == "full"`. This causes the system to incorrectly skip reading files that have only been partially read in their most recent access.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When a file's most recent read was partial (e.g., "10-50"), `should_read_file` should check if the requested range is covered by recent partial reads | The method returns `False` if ANY past entry (even old ones) has `lines_read == "full"` |
| The working memory should track the most recent state of file reads | The bug causes the system to think files are fully read when they were only partially read most recently |
| This leads to missing code that hasn't been read, causing incorrect assumptions and potential errors | |

## Root Cause
In the `should_read_file` method (lines 302-305):
```python
if match.lines_read.strip().lower() == "full":
    return False, "File already read (full)"
```
This check is inside a loop that iterates over `matches` (entries for the file in reverse chronological order). However, it returns `False` immediately when it finds ANY "full" entry, even if that's not the most recent entry. The correct logic should be: only return `False` if the FIRST (most recent) entry has `lines_read == "full"`.

## Fix Plan
1. Modify the `should_read_file` method to only return `False` for "full" reads when checking the most recent entry
2. If the most recent entry is not "full", continue to check partial reads as normal
3. Add a test case to verify the fix

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Fixed the bug in `should_read_file` method (line 270-274)
2. `tests/agents/test_working_memory.py` - Updated test expectations in `test_memory_should_read_file_full_then_partial` to match correct behavior

## Summary of Changes
The bug was in the `should_read_file` method which incorrectly returned `False` (skip reading) when a file was read fully in the past but partially more recently. The method checked if ANY entry had `lines_read == "full"`, instead of checking if the MOST RECENT entry had `lines_read == "full"`.

The fix changes the logic to only return `False` for "full" reads when the most recent entry indicates the file was read fully. This ensures that:
- If the most recent read was "full", all lines are considered already read
- If the most recent read was partial, we check if requested lines are covered by recent partial reads
- This aligns with the "working memory" concept of tracking recent access, not all-time access