# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T04:15:00+00:00
## Bug Summary
The `LineRange.from_str` method doesn't support multiple ranges (e.g., "10-20,30-40") even though this is a reasonable expectation for a working memory system tracking file reads. This causes `should_read_file` to incorrectly treat valid multi-range entries as invalid.

## Lens
**Lens 1: Logic Gaps** - The code doesn't handle a valid use case (multiple ranges in a single entry) that should be supported for tracking file reads.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `LineRange.from_str("10-20,30-40")` should parse into multiple ranges or at least the first valid range. | `LineRange.from_str("10-20,30-40")` returns `None`, causing the entire entry to be treated as invalid. |
| `should_read_file` should correctly handle entries with multiple ranges. | `should_read_file` returns "Cannot determine overlap - invalid lines_read format" for valid multi-range entries. |
| The working memory system should track which parts of a file have been read, including multiple disjoint sections. | The system only tracks single contiguous ranges per entry, limiting its usefulness. |

## Root Cause
The `LineRange.from_str` method is designed to parse single ranges like "10-20". It doesn't handle comma-separated multiple ranges. When `should_read_file` encounters an entry with `lines_read="10-20,30-40"`, it calls `LineRange.from_str` which returns `None`, causing `valid_ranges` to be empty. This leads to the method returning "Cannot determine overlap - invalid lines_read format" even though the entry contains valid range information.

## Fix Plan
1. Create a new method `parse_line_ranges` (plural) that parses comma-separated ranges and returns a list of `LineRange` objects.
2. Update `should_read_file` to use this new method instead of `LineRange.from_str`.
3. The new method should handle:
   - Single range: "10-20" → `[LineRange(10, 20)]`
   - Multiple ranges: "10-20,30-40" → `[LineRange(10, 20), LineRange(30, 40)]`
   - Single line: "10" → `[LineRange(10, 10)]`
   - "full" → empty list (special case)
   - Invalid formats → empty list

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Added `_parse_line_ranges` static method to parse comma-separated line ranges
   - Updated `should_read_file` method to use `_parse_line_ranges` instead of `LineRange.from_str`
   
2. `tests/agents/test_working_memory.py`:
   - Updated `test_parse_line_range_multiple_ranges` to test the new `_parse_line_ranges` method
   - Fixed a bug in `test_memory_should_read_file_invalid_lines_read_and_invalid_line_numbers` where it was using undefined variables

## Verification
- All tests pass (58/58)
- The new `_parse_line_ranges` method correctly handles:
  - Single range: "10-20" → `[LineRange(10, 20)]`
  - Multiple ranges: "10-20,30-40" → `[LineRange(10, 20), LineRange(30, 40)]`
  - Single line: "10" → `[LineRange(10, 10)]`
  - "full" → empty list
  - Invalid formats → empty list
- The `should_read_file` method now correctly processes entries with multiple ranges