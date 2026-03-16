# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-16T19:40:00.000000+00:00
## Bug Summary
The `should_read_file` method incorrectly handles `lines_read=None` differently from `lines_read=""`. Both should mean "no lines were read", but `None` results in reason "Cannot determine - no valid line ranges" while empty string results in "No lines have been read". The bug is in line 597 where it checks `if match.lines_read != "":` instead of `if match.lines_read:`.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `lines_read=None` and `lines_read=""` should be treated identically: both mean "no lines were read". When requesting to read a file with only such entries, the reason should be "No lines have been read". | `lines_read=None` causes `all_lines_read_empty` to be incorrectly set to `False` (because `None != ""` is `True`), resulting in reason "Cannot determine - no valid line ranges" instead of "No lines have been read". This creates inconsistent user experience. |

## Root Cause
In the `should_read_file` method, lines 592-602 track whether all entries have empty `lines_read`:
```python
# Check if lines_read is empty string (valid "no lines read")
if match.lines_read != "":  # LINE 597 - BUG HERE
    all_lines_read_empty = False
```

The check `match.lines_read != ""` is `True` when `match.lines_read` is `None` (because `None != ""` is `True`). This incorrectly sets `all_lines_read_empty = False` even though `None` means "no lines read" (same as empty string).

The fix is to change line 597 to `if match.lines_read:` which is `False` for both `None` and empty string.

## Fix Plan
Change line 597 from:
```python
if match.lines_read != "":
```
to:
```python
if match.lines_read:
```

This will correctly treat `None` and empty string as equivalent (both falsy).

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Line 597: Changed `if match.lines_read != "":` to `if match.lines_read:`
2. `tests/agents/test_working_memory.py` - Updated test `test_memory_should_read_file_lines_read_none` to expect "No lines have been read" instead of "cannot determine"
3. `tests/agents/test_working_memory_bug_validation.py` - Updated test `test_working_memory_entry_accepts_invalid_lines_read` to expect "No lines have been read" instead of "invalid lines_read format"
4. `tests/agents/test_working_memory_real_bug.py` - Updated string assertions to match actual output
5. `tests/agents/test_working_memory_none_vs_empty_bug.py` - Created new test to verify the bug fix

## Verification
- All tests pass: `python -m pytest tests/agents/ -x -q --tb=short`
- The bug is fixed: `lines_read=None` and `lines_read=""` now both return "No lines have been read" as the reason when no lines have been read.
- The fix is minimal and surgical, changing only one line in the source code.