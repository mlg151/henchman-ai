# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T12:00:00Z
## Bug Summary
The `should_read_file` method has a logic bug where it incorrectly handles the case when a file was read fully (`lines_read="full"`) but then later partially read again. The method only checks if the MOST RECENT entry has `lines_read="full"`, ignoring that older full reads should still count as the file having been fully read at some point.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| If a file was ever read fully (even if older entries), any line range should be considered already read | Method only checks most recent entry, causing unnecessary re-reading of lines that were previously read in full |
| Multiple partial reads that collectively cover a requested range should prevent re-reading | Method doesn't merge/check across all entries for the same file |
| Path normalization should ensure consistent file comparison | Paths are normalized but the method doesn't properly handle all entries for normalized path |

## Root Cause
The `should_read_file` method has several issues:
1. **Line 361-505**: The 143-line method is too complex (cyclomatic complexity 40) and has deep nesting (depth 6)
2. **Line 398-401**: Only checks `matches[0].lines_read` (most recent entry) for "full" read, ignoring older full reads
3. **Line 405-420**: When checking partial ranges, it collects `valid_ranges` from ALL entries but doesn't properly handle the case where an older full read should make all ranges covered
4. **Line 430-505**: The logic for checking if requested range is covered by merged ranges is overly complex and buggy

## Fix Plan
1. Simplify the `should_read_file` method by extracting helper functions
2. Fix the logic to check ALL entries for a file, not just the most recent
3. If ANY entry has `lines_read="full"` (case-insensitive, whitespace-normalized), the file should be considered fully read
4. For partial reads, merge ranges from ALL entries and check if requested range is covered
5. Add proper validation for line numbers before any other logic

## Status: IN PROGRESS