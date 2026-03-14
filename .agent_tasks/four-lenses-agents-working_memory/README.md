# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T16:30:00Z
## Bug Summary
The `should_read_file` method doesn't consider that multiple partial reads might collectively cover a requested line range. It only checks if a single entry covers the entire requested range, causing unnecessary re-reads when lines are covered across multiple entries.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| If lines 1-50 were read in entry A and lines 51-100 in entry B, requesting lines 1-100 should return False (skip) | Returns True (should read) because no single entry covers 1-100 |
| Multiple partial reads that collectively cover all requested lines should prevent re-reading | Only checks individual entries, not collective coverage |
| File reading decisions should be accurate based on complete read history | Inaccurate decisions waste context window and reduce performance |

## Root Cause
The bug is in the logic of `should_read_file` method at lines 280-285:
```python
# Check ALL entries for line range containment
for match in matches:
    rng = LineRange.from_str(match.lines_read)
    if rng:
        found_valid_range = True
        if requested.start >= rng.start and requested.end <= rng.end:
            return False, "File already read (contained within previously read lines)"
```

The method only checks if a SINGLE entry covers the ENTIRE requested range. It doesn't consider that multiple entries might collectively cover the range. For example:
- Entry 1: lines 1-50
- Entry 2: lines 51-100
- Requested: lines 1-100

Current logic: Checks entry 1 (1-100 not contained in 1-50) → NO, checks entry 2 (1-100 not contained in 51-100) → NO, returns True (should read).

Expected logic: Should recognize that entries 1+2 collectively cover 1-100, return False (skip).

## Fix Plan
Modify the `should_read_file` method to track which lines have been read across ALL entries and check if the requested range is fully covered by the union of all read ranges.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `should_read_file` method to collect all valid line ranges, merge overlapping/adjacent ranges, and check if requested range is fully covered by the union of ranges.
2. `tests/agents/test_working_memory.py` - Added new test `test_memory_should_read_file_multiple_partials_cover_range` to verify the fix.

## Changes Made
The bug was in the logic of `should_read_file` method. Changed from checking if a SINGLE entry covers the entire requested range to:

1. Collecting all valid line ranges from all entries for the file
2. Sorting ranges by start line
3. Merging overlapping or adjacent ranges (ranges that touch or overlap are combined)
4. Walking through merged ranges to check if the requested range is fully covered

Key changes in the algorithm:
- Old: Check each entry individually: `if requested.start >= rng.start and requested.end <= rng.end`
- New: Merge ranges first, then check coverage: walk through merged ranges tracking which lines are covered

Example fix for the bug case:
- Entry 1: lines 1-50
- Entry 2: lines 51-100  
- Requested: lines 1-100

Old logic: Checks entry 1 (1-100 not in 1-50) → NO, checks entry 2 (1-100 not in 51-100) → NO, returns True (should read)
New logic: Merges 1-50 and 51-100 into 1-100, checks if requested 1-100 is covered → YES, returns False (skip)

This prevents unnecessary re-reading when lines are covered across multiple partial reads, improving performance and reducing context window waste.