# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-13T18:30:00+00:00
## Bug Summary
The `LineRange` class allows invalid ranges where `start > end`, and the `overlaps` method gives incorrect results for such invalid ranges. This can lead to incorrect logic in `should_read_file` when comparing line ranges.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `LineRange` should represent a valid line range where `start <= end`. | `LineRange` allows `start > end`, creating invalid ranges. |
| `LineRange.overlaps()` should correctly determine if two valid ranges overlap. | `overlaps()` gives incorrect results when either range has `start > end`. |
| `should_read_file` should work correctly with valid line ranges. | `should_read_file` can produce incorrect results when given or comparing against invalid ranges. |

## Root Cause
The `LineRange` dataclass doesn't validate that `start <= end` in its constructor. The `overlaps` method assumes `self.start <= self.end` and `other.start <= other.end`, but this assumption is not enforced. When `start > end`, the logic `self.start <= other.end and self.end >= other.start` can produce incorrect results.

## Fix Plan
Add validation to `LineRange` to ensure `start <= end`. Options:
1. Add `__post_init__` method to validate `start <= end` and raise `ValueError` if invalid.
2. Or fix `overlaps` method to handle invalid ranges (but this doesn't fix the root issue).
3. Or fix `should_read_file` to validate `start <= end` before creating `LineRange`.

The cleanest fix is option 1: validate in `LineRange.__post_init__`.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Added `__post_init__` method to `LineRange` class to validate `start <= end`
   - Updated `from_str` method to catch `ValueError` from `__post_init__` validation
   - Added validation in `should_read_file` to check `start <= end` before creating `LineRange`
2. `tests/agents/test_working_memory.py`:
   - Added `test_line_range_invalid_start_gt_end` test to verify validation
   - Test expects `ValueError` when creating `LineRange` with `start > end`
   - Test expects `from_str("50-10")` to return `None` for invalid range