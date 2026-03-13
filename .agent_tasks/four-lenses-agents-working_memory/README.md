# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-13T19:00:00Z
## Bug Summary
When the same file appears multiple times in `recent_files` (e.g., read at different times with different line ranges), the `should_read_file` method finds the FIRST (oldest) matching entry instead of the MOST RECENT, causing incorrect decisions about whether to re-read the file.

## Lens
The Intent vs. Reality Check - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When checking if a file should be read, the system should consider the MOST RECENT read of that file (what was most recently cached) | The system finds the FIRST matching entry (oldest), which may have been pruned or contain outdated line range information |
| If a file was read lines 60-100 most recently, and we ask for lines 70-90, should return `False` (already read) | Returns `True` because it finds older entry for lines 1-50 and checks against that |
| Working memory should track current state, not historical state | System makes decisions based on stale data |

## Root Cause
In `should_read_file` method (line 247), the code uses `next((e for e in self.recent_files if e.path == path), None)` which finds the first matching entry from the beginning of the list. Since `recent_files` is appended to (new entries at end), the first match is the OLDEST entry for that file.

The `update_after_read` method always adds new entries instead of updating existing ones, allowing multiple entries for the same file.

## Fix Plan
Change `should_read_file` to search from the end: `next((e for e in reversed(self.recent_files) if e.path == path), None)` to find the most recent entry.

Alternatively (better), change `update_after_read` to update existing entry instead of adding new one, but that's a larger change. The minimal fix is to search from end.

## Status: IN PROGRESS