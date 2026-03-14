# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T06:15:00Z
## Bug Summary
The `should_read_file` method incorrectly returns `False` (already read) when a file has an older entry with `lines_read='full'` and a newer entry with a partial line range. The method should only consider the MOST RECENT entry when determining if a file was read "fully", but it checks ALL entries and returns `False` if ANY entry has `lines_read='full'`.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gap

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When a file has multiple entries, `should_read_file` should only consider the MOST RECENT entry for "full" status. If the most recent entry is not "full", proceed to line range logic. | The method checks ALL entries for "full" status. If ANY entry (even older ones) has `lines_read='full'`, it returns `False` (already read). |
| If file was read fully in the past but more recently read partially, the most recent (partial) information should take precedence. | Older "full" entry overrides newer partial entry, causing the method to incorrectly claim lines outside the partial range are already read. |

## Root Cause
In the `should_read_file` method:
1. Line 251: `matches = [e for e in reversed(self.recent_files) if e.path == path]` creates list with newest entries first
2. Lines 256-259: Loop checks EACH match for `lines_read == "full"`. If ANY match is "full", returns `False`
3. The bug: It checks ALL matches, not just the first (most recent) one
4. Result: Older "full" entry causes method to return `False` even when most recent entry is partial

The fix: Only check the FIRST (most recent) match for "full" status. If first match is not "full", proceed to line range logic.

## Fix Plan
1. Modify `should_read_file` to only check the FIRST match (most recent entry) for `lines_read == "full"`
2. Remove the loop that checks ALL matches for "full" status
3. Update logic to prioritize most recent information over older information

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Lines 256-259: Replaced loop checking ALL matches for "full" with single check of first match
   - Lines 263-266: Removed redundant loop (was checking matches again after already checking first match)

## Test Case That Demonstrates the Bug
```python
memory = WorkingMemory(current_task="Test")
# Older entry: file read fully
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Old full read", "full"))
# Newer entry: file read partially  
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "New partial read", "10-50"))

# Ask for lines 60-80 (not in newer partial read)
should_read, reason = memory.should_read_file("/test/file.py", 60, 80)
# Before fix: Returns False (finds older "full" entry)
# After fix: Returns True (most recent entry doesn't cover lines 60-80)
```

## Verification
- Created test `test_bug_verification.py` that demonstrates the bug
- Modified `should_read_file` method to only check first (most recent) match for "full" status
- Removed redundant loop checking all matches
- Ran all tests: `pytest tests/agents/test_working_memory.py` - ALL TESTS PASS
- Verified bug is fixed: `test_bug_verification.py` now passes