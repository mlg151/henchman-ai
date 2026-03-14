# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-14T23:20:00Z
## Bug Summary
The `should_read_file` method incorrectly handles partial line range specifications (when only `start` or only `end` is provided). It returns `True` (should read) without checking if the requested partial range has already been read, leading to unnecessary file re-reads.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic gap in handling edge cases for partial line range specifications.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `start=10, end=None` (read from line 10 to EOF), method should check if lines 10-EOF have been read | Method returns `True` immediately without checking coverage |
| When `start=None, end=50` (read from beginning to line 50), method should check if lines 1-50 have been read | Method returns `True` immediately without checking coverage |
| Method should validate line numbers even when only one is provided | Method only validates if BOTH are provided |
| Method should provide accurate reason for decision | Returns misleading "File not fully read - partial read recorded" even when specific lines might have been read |

## Root Cause
The method has an early return at line 298-300:
```python
if start is None or end is None:
    # No line range specified but file wasn't read fully
    return True, "File not fully read - partial read recorded"
```

This assumes that if either `start` or `end` is `None`, we want to read the entire file. But actually:
- `start=10, end=None` means "read from line 10 to end of file"
- `start=None, end=50` means "read from beginning to line 50"

The method should handle these cases by checking if the requested partial range is covered by existing reads.

## Fix Plan
1. Handle the three cases separately: both provided, only start provided, only end provided
2. For `start=10, end=None`: check if lines 10 through max(read_end) have been read
3. For `start=None, end=50`: check if lines min(read_start) through 50 have been read  
4. Update validation to check line numbers even when only one is provided
5. Provide more accurate reason messages

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Fixed `should_read_file` method to handle partial range specifications intelligently
2. `tests/agents/test_working_memory.py` - Updated tests to match new behavior

## Changes Made
1. Moved `valid_ranges` computation earlier in `should_read_file` method
2. Added intelligent handling for partial range specifications:
   - `start=X, end=None`: Checks if we've read from X to max(read_end), returns "May need to read lines beyond {max_read_end}" or "Start line {start} beyond last read line {max_read_end}"
   - `start=None, end=Y`: Checks if we've read from min(read_start) to Y, returns "May need to read lines before {min_read_start}" or "End line {end} before first read line {min_read_start}"
3. Updated test expectations to match new, more accurate error messages
4. Fixed a bug where the check for "full" file read was accidentally removed (restored it)

## Verification
- All 55 tests in `tests/agents/test_working_memory.py` pass
- The fix provides more accurate error messages for partial range specifications
- The method still correctly handles the "full" file read case
- The method still validates line numbers even when only one is provided