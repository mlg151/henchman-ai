# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2024-03-14T20:15:00Z
## Bug Summary
The `should_read_file` method incorrectly handles the case when a file was read fully (`lines_read="full"`) followed by a partial read. It returns `False` for any line range when the most recent entry is "full", but returns `True` for lines outside the partial read when the most recent entry is partial (even if an older entry was "full").

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When a file was read fully in the past but partially more recently, the system should only consider lines that were read in the most recent partial read as "already read". | The system incorrectly returns `False` for any line range when checking against a "full" entry, even if that "full" entry is older than a more recent partial entry. |
| The `should_read_file` method should check ALL entries for a file (not just the most recent) to determine if requested lines are covered. | The method only checks the most recent entry when it's "full", but should check all entries when it's partial to see if requested lines are covered by any combination of entries. |
| Case-insensitive "full" detection should handle whitespace variations. | The method uses `strip().lower()` which handles whitespace, but there's a bug in the logic flow. |

## Root Cause
The bug is in the `should_read_file` method at lines 245-329. The logic flow is:

1. Find all entries for the file (most recent first)
2. If no entries, return `True` (read)
3. Check if most recent entry has `lines_read.strip().lower() == "full"` - if yes, return `False` (skip)
4. If no line range specified but file wasn't read fully, return `True` (read)
5. Validate line range
6. Collect all valid line ranges from all entries
7. Check if requested range is fully covered by any single entry
8. Merge overlapping ranges
9. Check if requested range is fully covered by merged ranges

The bug is in step 3: it returns `False` immediately if the most recent entry is "full", without considering that there might be more recent partial entries (which there aren't since we're checking most recent first, but the logic should be: if most recent is "full", file is fully read, return False).

Actually, looking more carefully: the test `test_memory_should_read_file_full_then_partial_bug` reveals the real issue. The test adds a "full" entry, then a "partial" entry (10-50). When checking lines 1-100, it should return `True` because the most recent read was partial (10-50), not full. But the current code would find the most recent entry (which is partial, 10-50), check if it's "full" (it's not), then proceed to check line ranges. However, there's another issue: when checking if lines are covered, it only checks if they're contained within a single entry, not if they're covered by multiple entries together.

Actually wait, let me trace through the actual bug. Looking at the test failures in the test file, I see multiple tests marked as "BUG" with comments. Let me examine the actual implementation more carefully.

## Fix Plan
I need to:
1. Read the actual implementation carefully
2. Identify the exact bug (there are multiple test failures marked as BUG)
3. Write a failing test that demonstrates the bug
4. Fix the bug
5. Verify all tests pass

The main issues appear to be:
1. Case-insensitive "full" detection (handles whitespace with `strip().lower()`)
2. Checking all entries, not just most recent, when determining if lines are covered
3. Properly merging ranges from multiple entries to determine coverage

## Status: IN PROGRESS