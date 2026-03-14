# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T18:00:00Z
## Bug Summary
The `should_read_file` method incorrectly handles case-insensitive "full" file reads and fails to check all historical entries for a file, causing unnecessary re-reading of already-read content.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When a file is marked as "full", "FULL", or "Full" (case-insensitive), any subsequent read should be skipped | Only exact lowercase "full" is recognized, causing unnecessary re-reads |
| When checking if lines have been read, the method should consider ALL historical entries for the file, not just the most recent | Only checks most recent entry, causing re-reading of lines that were read in earlier operations |
| When multiple partial reads collectively cover a requested range, the method should return False (already read) | Returns True because no single entry covers the entire range |

## Root Cause
The `should_read_file` method has several logic gaps:
1. **Case sensitivity bug**: Line 249 checks `match.lines_read.strip().lower() == "full"` but the actual check at line 251 uses `match.lines_read.strip().lower() == "full"` - this is correct but the test shows uppercase "FULL" isn't handled properly in practice.
2. **Single-entry checking**: The method only checks if ANY entry indicates "full" read, but when checking line ranges, it doesn't properly merge and check across all historical entries.
3. **Incomplete range merging**: The range merging logic (lines 284-302) attempts to merge ranges but the coverage checking logic (lines 304-322) is flawed and doesn't properly handle gaps between merged ranges.

## Fix Plan
1. Fix the case-insensitive "full" check to properly handle all case variations and whitespace.
2. Modify the logic to check ALL historical entries for a file, not just stop at the first "full" check.
3. Improve the range coverage algorithm to properly determine if requested lines are covered by the union of all historical reads.

## Status: IN PROGRESS