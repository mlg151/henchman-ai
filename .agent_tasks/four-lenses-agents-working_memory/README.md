# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2024-01-15T00:00:00Z
## Bug Summary
The `_parse_line_ranges` static method in `WorkingMemory` class has a critical bug where it returns an empty list if ANY part of the `lines_read` string is invalid, instead of skipping invalid parts and returning valid ranges. This causes the `should_read_file` method to incorrectly report "Cannot determine - invalid lines_read format" even when there are valid line ranges recorded.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

The code assumes that if any part of a comma-separated `lines_read` string is invalid, the entire string is invalid. This is a logical gap because:
1. A `lines_read` string like "10-50,0-5,60-100" contains valid ranges (10-50, 60-100) and one invalid range (0-5)
2. The method should parse and return the valid ranges, not discard everything
3. This bug causes unnecessary file re-reading when partial valid information exists

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `_parse_line_ranges("10-50,0-5,60-100")` should return `[LineRange(10, 50), LineRange(60, 100)]` (skipping invalid 0-5) | Returns empty list `[]`, discarding all valid ranges |
| `_parse_line_ranges("10-50,abc,60-100")` should return `[LineRange(10, 50), LineRange(60, 100)]` (skipping non-integer "abc") | Returns empty list `[]`, discarding all valid ranges |
| `should_read_file` should use valid ranges even when some parts are invalid | Returns `True` with "Cannot determine - invalid lines_read format", causing unnecessary re-reading |

## Root Cause
The bug is in the `_parse_line_ranges` method at lines 343 and 351. When parsing comma-separated parts:
1. If ANY part has invalid line numbers (e.g., 0-5 where 0 < 1), the method returns empty list `return []` (line 343)
2. If ANY part cannot be parsed as integer (e.g., "abc"), the method returns empty list `return []` (line 348, 356)
3. The method should accumulate valid ranges and skip invalid ones, not fail entirely

This bug affects `should_read_file` because when `valid_ranges` is empty (due to this bug), the method returns `True` with "Cannot determine - invalid lines_read format", even though there are valid ranges that could be used to determine if lines have been read.

## Fix Plan
1. Fix `_parse_line_ranges` to skip invalid parts instead of returning empty list
2. Accumulate valid ranges in a list, skip invalid parts with `continue`
3. Return the list of valid ranges (could be empty if ALL parts are invalid)
4. Update `should_read_file` to handle the case where some entries have valid ranges and others don't
5. Add comprehensive tests to verify the fix

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Fixed `_parse_line_ranges` method to skip invalid parts instead of returning empty list
2. `tests/agents/test_working_memory.py` - Updated test `test_memory_parse_line_ranges_invalid_parts_silently_ignored_bug` to reflect correct behavior
3. `tests/agents/test_working_memory_parse_bug.py` - Added new test file to verify the fix

## Verification
- All existing tests pass (63 tests in `test_working_memory.py`)
- New test `test_working_memory_parse_bug.py` passes (2 tests)
- The fix correctly handles mixed valid/invalid `lines_read` strings:
  - `"10-50,0-5,60-100"` → Returns `[LineRange(10, 50), LineRange(60, 100)]` (skips invalid 0-5)
  - `"10-50,abc,60-100"` → Returns `[LineRange(10, 50), LineRange(60, 100)]` (skips non-integer "abc")
  - `"10-50,60-55,70-100"` → Returns `[LineRange(10, 50), LineRange(70, 100)]` (skips invalid 60-55 where start > end)
  - `"0-5,abc,10-5"` → Returns `[]` (all parts invalid)
  - `"10-20-30"` → Returns `[]` (invalid format with multiple dashes)