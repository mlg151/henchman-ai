# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T03:00:00Z
## Bug Summary
The `should_read_file` method returns misleading error messages for partial range requests (`start=X, end=None` or `start=None, end=Y`). When the requested line is in a gap between read ranges, the error message incorrectly refers to lines "beyond" or "before" the read ranges instead of identifying the gap.

## Lens
**Phase 1: Logic Gaps** - The code assumes a "happy path" where the requested line is either within a read range or beyond the extremes, but doesn't properly handle the case where the line is in a gap between read ranges.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `start=70, end=None` and read ranges are 1-50, 80-100, message should indicate line 70 is in a gap | Message says "May need to read lines beyond 100" (incorrect) |
| When `start=None, end=70` and read ranges are 1-50, 80-100, message should indicate lines 51-70 are in a gap | Message says "May need to read lines before 1" (incorrect) |
| Error messages should help users understand WHY reading is needed | Misleading messages make debugging difficult |

## Root Cause
The logic for partial range requests uses `max_read_end` and `min_read_start` comparisons without checking if the requested line falls within the union of merged read ranges. When `start=X` is compared to `max_read_end`, if `X <= max_read_end`, it assumes the line might be within a read range (or beyond it). But it doesn't check if `X` is actually in a gap between ranges.

## Fix Plan
1. For `start=X, end=None`: Check if line X is within any merged read range using the existing `_merge_ranges` and gap-checking logic
2. For `start=None, end=Y`: Check if line Y is within any merged read range using the existing `_merge_ranges` and gap-checking logic  
3. Update error messages to accurately describe gaps when they exist

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Added `_merge_ranges` static method to consolidate merging logic
   - Updated `should_read_file` method to provide accurate error messages for gaps in partial range requests
   - When `start=X, end=None` and line X is in a gap, message now says "Start line X in gap between lines Y and Z" instead of "May need to read lines beyond max_read_end"
   - When `start=None, end=Y` and line Y is in a gap, message now says "End line Y in gap between lines A and B" instead of "May need to read lines before min_read_start"
   
2. `tests/agents/test_working_memory.py`:
   - Added `test_memory_should_read_file_partial_range_gap_messages` test to verify accurate error messages for gaps