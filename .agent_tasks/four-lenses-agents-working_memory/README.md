# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T19:00:00Z
## Bug Summary
The `should_read_file` method fails to recognize `lines_read` values like `"full,10-20"` as indicating the file was read fully. It only checks if the entire normalized string equals `"full"`, not if it contains `"full"` as a token. This causes incorrect behavior where a file marked as `"full,10-20"` (contradictory but containing "full") is not considered fully read.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| If `lines_read` contains "full" as a token (e.g., `"full"`, `"full,10-20"`, `"10-20,full"`), the file should be considered fully read | Only exact match `"full"` (after normalization) is recognized as "file read fully" |
| Contradictory `lines_read` values like `"full,10-20"` should either be rejected as invalid or treated as "full" (since "full" takes precedence) | `"full,10-20"` is parsed as line range 10-20 only, ignoring the "full" token |
| The presence of "full" should override any line range specifications | Line ranges in `"full,10-20"` are parsed and checked, leading to incorrect "should read" decisions |

## Root Cause
In `should_read_file` method lines 410-420:
```python
normalized = "".join(match.lines_read.split()).lower()
if normalized == "full":
    return False, "File already read (full)"
```
The check is for exact equality `normalized == "full"`. For `lines_read="full,10-20"`, normalization produces `"full,10-20"` which doesn't equal `"full"`.

The `_parse_line_ranges` method also has issues: for `"full,10-20"`, it splits by comma to get `["full", "10-20"]`, tries to parse `"full"` as integer (fails), skips it, then parses `"10-20"` as a line range. So it ignores the "full" token.

## Fix Plan
1. Modify the "full" check in `should_read_file` to check if `lines_read` contains "full" as a token (after splitting by comma and normalizing)
2. Update `_parse_line_ranges` to return empty list (or special value) when "full" is present
3. Consider adding validation to `WorkingMemoryEntry` to reject contradictory `lines_read` values

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Line 413: Changed `if normalized == "full":` to `if normalized == "full" or "full" in normalized.split(","):`
   - Line 324: Changed `if normalized == "full":` to `if normalized == "full" or "full" in normalized.split(","):`

## Test Files Created
1. `tests/agents/test_working_memory_full_token_bug.py` - Contains 6 tests that demonstrate the bug and verify the fix
2. `tests/agents/test_working_memory_full_contains_bug.py` - Additional tests for the bug

## Verification
- All existing tests pass (111 tests in working_memory test suite)
- New bug-specific tests pass
- The fix correctly handles:
  - `"full,10-20"` → file considered fully read
  - `"10-20,full"` → file considered fully read  
  - `"full , 10-20"` (with spaces) → file considered fully read
  - `"FULL,10-20"` (uppercase) → file considered fully read
  - `"full"` (exact) → still works
  - `"  full  "` (with spaces) → still works