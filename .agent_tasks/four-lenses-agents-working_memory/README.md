# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T00:00:00Z
## Bug Summary
The `get_file_insights` method incorrectly returns insights from the first (oldest) matching file entry instead of the most recent one, inconsistent with `should_read_file` which correctly finds the most recent entry.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When a file has been read multiple times, `get_file_insights` should return insights from the most recent read | Returns insights from the first (oldest) read |
| Consistency: `should_read_file` uses `reversed()` to find most recent entry, `get_file_insights` should do the same | Inconsistent behavior between related methods |
| If file was read at time T1 with insights I1, then read again at T2 with insights I2, querying insights should return I2 | Returns I1 (stale insights) |

## Root Cause
The `get_file_insights` method uses `next((e.key_insights for e in self.recent_files if e.path == path), [])` which iterates through `recent_files` in insertion order (oldest to newest). When it finds the first match, it returns those insights. However, `recent_files` is a list where new entries are appended, so the most recent entry is at the end. The method should iterate in reverse order (newest to oldest) like `should_read_file` does.

## Fix Plan
Change `get_file_insights` to use `reversed(self.recent_files)` to find the most recent entry, matching the behavior of `should_read_file`.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `get_file_insights` method to use `reversed(self.recent_files)` instead of `self.recent_files`
2. `tests/agents/test_working_memory.py` - Added new test `test_memory_get_file_insights_multiple_entries` to verify the fix and prevent regression

## Fix Details
The fix was minimal and surgical:
- Changed line in `get_file_insights` method from:
  ```python
  return next((e.key_insights for e in self.recent_files if e.path == path), [])
  ```
  to:
  ```python
  return next((e.key_insights for e in reversed(self.recent_files) if e.path == path), [])
  ```

This ensures consistency with the `should_read_file` method which already uses `reversed(self.recent_files)` to find the most recent entry for a file.

The new test verifies that when a file has multiple entries, `get_file_insights` returns insights from the most recent (last added) entry rather than the oldest (first added) entry.