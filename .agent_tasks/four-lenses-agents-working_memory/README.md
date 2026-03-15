# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T21:15:00Z
## Bug Summary
The `should_read_file` method incorrectly rejects `end=-1` as an invalid line number, when `end=-1` is a valid special value that means "read to end of file" in the `read_file` tool.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gap where the code assumes all line numbers must be positive (≥1), but `end=-1` is a special sentinel value that should be allowed.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `end=-1` should be accepted as valid (means "read to end of file") | `end=-1` is rejected with "Invalid line number: end must be positive (1-indexed), got end=-1" |
| The working memory system should be compatible with the `read_file` tool API | Incompatibility causes false positives in `should_read_file` when checking if a file needs to be read |
| Special sentinel values should be handled before general validation | General validation `end < 1` incorrectly catches the special case |

## Root Cause
The validation logic in `should_read_file` checks `if end < 1:` and returns an error. However, `end=-1` is a special sentinel value used by the `read_file` tool to mean "read to end of file". The working memory system should accept the same parameters as the tools it tracks.

## Fix Plan
1. Modify the validation for `end` parameter to allow `end=-1` as a special case
2. Keep validation for `start` parameter strict (must be ≥1)
3. Update the validation logic to check `if end < 1 and end != -1:` instead of just `if end < 1:`
4. Ensure the logic for comparing line ranges handles `end=-1` correctly (treat as "to end of file")

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified validation logic to accept `end=-1` as valid (converted to `None` internally)
2. `tests/agents/test_working_memory_bug_validation_order.py` - Updated test expectations for `end=-1` (now valid)
3. `tests/agents/test_working_memory_four_lenses_real_bug.py` - Updated test expectations for `end=-1` (now valid)

## Changes Made
1. In `should_read_file` method:
   - Changed validation for `end` parameter from `if end < 1:` to `if end < 1 and end != -1:` to allow `end=-1`
   - Added conversion logic: `if end == -1: end = None` to treat `end=-1` as "read to end of file" (same as `end=None`)
2. Updated test files to reflect that `end=-1` is now valid (not invalid)

## Verification
- All existing tests pass (676 tests)
- The bug test `test_memory_should_read_file_end_minus_one_bug` now passes
- The working memory system is now compatible with the `read_file` tool API which uses `end=-1` as default value