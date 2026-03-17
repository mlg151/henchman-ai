# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-01-15T00:00:00Z
## Bug Summary
The `_read_context_file_content` function has a potential race condition and file reading issue where `path.stat()` may succeed but `path.read_text()` could fail due to file being deleted or permissions changing between the two async operations.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps: The code assumes a "happy path" where if `path.stat()` succeeds, then `path.read_text()` will also succeed. This is not guaranteed in concurrent environments.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| File reading should handle all possible failure modes gracefully | If file is deleted between stat() and read_text(), the function will crash with unhandled exception |
| Context tree should show error message for unreadable files | Unhandled exception propagates up, potentially crashing UI |

## Root Cause
The function performs two separate async operations (`stat()` then `read_text()`) without wrapping the second operation in proper error handling. Between these two async calls, the file could be deleted, permissions could change, or the file could become unreadable.

## Fix Plan
Wrap the `path.read_text()` call in a try-except block to handle potential `OSError` and `UnicodeDecodeError` exceptions. Return an appropriate error message instead of letting the exception propagate.

## Status: FIXED

## Files Changed
1. `src/henchman/cli/textual_mixins.py` - Modified `_read_context_file_content` function to add error handling for `read_text()` failures
2. `tests/cli/test_textual_mixins_coverage.py` - Added test `test_read_text_fails_after_stat_succeeds` to verify the fix

## Verification
- Added failing test that demonstrates the bug (raises OSError when read_text fails after stat succeeds)
- Implemented fix with proper error handling for both stat() and read_text() operations
- All existing tests pass
- New test passes with the fix