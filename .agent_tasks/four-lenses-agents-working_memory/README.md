# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-13T16:20:00Z
## Bug Summary
The `should_read_file()` method incorrectly returns `False` when checking if overlapping line ranges need to be read. It uses `LineRange.overlaps()` which returns `True` if ranges overlap at all, but should check if the **requested range is fully contained within** the previously read range.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| If file was previously read with lines 10-50 and we want to read lines 1-100, we SHOULD read it because we need lines 1-9 and 51-100. The method should return `True`. | The method returns `False` because ranges 10-50 and 1-100 overlap. This causes missing code that hasn't been read yet, potentially leading to incorrect decisions or incomplete understanding. |

## Root Cause
In `should_read_file()` method line 246:
```python
if rng and rng.overlaps(LineRange(start, end)):
    return False, "File already read (overlapping lines)"
```
The `overlaps()` method returns `True` if ranges share any lines. But we need to check if the requested range is **fully contained within** the previously read range. If previously read 10-50 and requested 1-100, they overlap but 1-100 is NOT fully contained in 10-50, so we should read it.

## Fix Plan
1. Change the logic from `rng.overlaps(...)` to check if requested range is fully contained within previously read range
2. Add a helper method `contains()` to `LineRange` class or compute: `requested.start >= rng.start and requested.end <= rng.end`
3. Update tests to verify the fix
4. Also fix the misleading reason for invalid `lines_read` format

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Fixed `should_read_file()` method to check if requested range is fully contained within previously read range instead of just overlapping
2. `tests/agents/test_working_memory.py` - Updated tests to reflect correct behavior:
   - `test_memory_should_read_file_overlapping_lines`: Changed expected result from `False` to `True` (lines 30-70 not fully contained in 10-50)
   - `test_memory_should_read_file_with_multiple_entries`: Changed expected result from `False` to `True` (lines 60-150 not fully contained in 1-100)
   - `test_memory_should_read_file_different_lines`: Updated reason assertion
   - `test_memory_should_read_file_invalid_lines_read`: Updated reason assertion
   - Added new test `test_memory_should_read_file_overlap_but_not_contained` to verify the fix

## Summary
The bug was that `should_read_file()` incorrectly returned `False` when line ranges overlapped but the requested range wasn't fully contained within the previously read range. For example, if file was read with lines 10-50 and we want to read lines 1-100, the method should return `True` (need lines 1-9 and 51-100) but it returned `False`. The fix changes the logic from checking `overlaps()` to checking if requested range is fully contained within previously read range.