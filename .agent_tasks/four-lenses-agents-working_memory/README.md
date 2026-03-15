# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T15:00:00Z
## Bug Summary
The `_parse_line_ranges` method silently ignores invalid parts in the `lines_read` string (e.g., "10-20-30" or "invalid-format") without any indication, which can lead to incorrect behavior in `should_read_file` when mixed valid and invalid ranges are provided.

## Lens
**Phase 1: The Intent vs. Reality Check** - The method assumes all input is valid or can be safely ignored, but silently ignoring invalid parts can lead to incorrect conclusions about what lines were actually read.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Invalid `lines_read` format should be rejected or at least logged | Invalid parts are silently ignored |
| Method should return error/None for invalid input | Returns partial results for mixed valid/invalid input |
| Callers should know when input is invalid | Callers may think invalid input was parsed correctly |

## Root Cause
In `_parse_line_ranges`, when parsing parts split by commas, if a part doesn't match the expected format (e.g., "10-20-30" has multiple dashes, "invalid-format" has no dash), the method catches the `ValueError` from `int()` conversion and `continue`s, silently skipping the invalid part. This means `"1-10,20-30,40-50-60"` returns `[LineRange(1,10), LineRange(20,30)]` without any indication that `"40-50-60"` was invalid.

## Fix Plan
1. Modify `_parse_line_ranges` to return empty list when ANY part is invalid
2. Update `should_read_file` to handle the new behavior (already handles empty list as invalid)

## Fix Implementation
Changed `continue` statements to `return []` in `_parse_line_ranges` method. Now when any part of the `lines_read` string is invalid (e.g., non-integer, negative line numbers, start > end, multiple dashes), the entire method returns empty list `[]` instead of silently ignoring invalid parts and returning partial results.

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `_parse_line_ranges` method to return empty list when any part is invalid
2. `tests/agents/test_working_memory.py` - Added test `test_memory_parse_line_ranges_invalid_parts_silently_ignored_bug` to verify the fix

## Status: FIXED