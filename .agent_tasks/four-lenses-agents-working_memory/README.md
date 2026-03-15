# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2024-01-15T00:00:00Z
## Bug Summary
The `should_read_file` method in `WorkingMemory` class has a critical bug where it only checks the MOST RECENT entry for a file when determining if lines have been read, ignoring older entries that may contain "full" reads or partial reads that collectively cover the requested range.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

The code assumes that only the most recent file read matters for determining if lines have been read. This is a logical gap because:
1. If a file was read "fully" at any point in the task history, ALL lines should be considered read
2. Multiple partial reads can collectively cover a requested range
3. The method should consider ALL historical entries for a file, not just the most recent

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| If ANY entry for a file has `lines_read="full"`, the file should be considered fully read for ALL line ranges | Only checks most recent entry for "full", causing unnecessary re-reading of lines that were previously read in full |
| Multiple partial reads that collectively cover a requested range should prevent re-reading | Only checks most recent partial read, causing unnecessary re-reading even when lines were covered by older entries |
| Case-insensitive "full" detection (FULL, Full, full) | Only matches lowercase "full", causing unnecessary re-reading |
| All entries for a file should be considered when determining line coverage | Only considers most recent entry, leading to inefficient file reading patterns |

## Root Cause
The bug is in the `should_read_file` method at line 360. The method:
1. Finds ALL matching entries for a file (`matches = [e for e in reversed(self.recent_files) if e.path == normalized_path]`)
2. But then only checks the FIRST (most recent) match for "full": `if isinstance(match.lines_read, str) and "".join(match.lines_read.split()).lower() == "full":`
3. Actually, it has a loop that checks ALL matches for "full", but the logic is flawed - it returns immediately when it finds a "full" in ANY match, which is CORRECT for the "full" check
4. However, for partial reads, it collects ranges from ALL matches but then doesn't properly check if the requested range is covered by the UNION of all ranges

The real issue is in the logic for checking if a requested range is covered by merged ranges from all entries. The algorithm for checking coverage is complex and buggy.

## Fix Plan
1. Fix the logic in `should_read_file` to properly check if a requested range is fully covered by the union of all line ranges from ALL entries for that file
2. Ensure "full" detection is case-insensitive and works for ANY entry (already works)
3. Improve the algorithm for checking range coverage to handle gaps between ranges correctly
4. Add comprehensive tests to verify the fix

## Status: IN PROGRESS