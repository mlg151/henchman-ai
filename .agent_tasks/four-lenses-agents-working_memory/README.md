# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-16T05:25:00Z
## Bug Summary
`WorkingMemoryEntry` doesn't validate `lines_read` content when created. It only checks that `lines_read` is a string or `None`, but doesn't validate that the string contains valid line ranges. This allows invalid data like `lines_read="0-10"` (line 0 is invalid, lines are 1-indexed) to be stored, causing `should_read_file` to fail silently later.

## Lens
Phase 1: The Intent vs. Reality Check - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `WorkingMemoryEntry` should validate `lines_read` format when created | ❌ Only validates type (string/None), not content |
| Invalid `lines_read` like "0-10" should be rejected immediately | ❌ Accepted, causes error later in `should_read_file` |
| Error messages should be clear and actionable | ❌ `should_read_file` returns "Cannot determine - invalid lines_read format" without details |
| Data integrity: invalid data shouldn't be stored | ❌ Invalid `lines_read` stored, causes silent failure later |

## Root Cause
1. `WorkingMemoryEntry.__post_init__` only validates `lines_read` is a string or `None` (line 67-73)
2. It doesn't call `_parse_line_ranges` to validate the format
3. `_parse_line_ranges` creates `LineRange` objects which validate in `__post_init__`, raising `ValueError` for invalid line numbers
4. `should_read_file` catches `ValueError` from `_parse_line_ranges` and skips the entry (line 461-464)
5. This causes the file to be treated as not read, with unclear error message

## Fix Plan
1. Add validation in `WorkingMemoryEntry.__post_init__`: call `_parse_line_ranges(self.lines_read)` (or a validation helper)
2. Raise `ValueError` with clear message if `lines_read` is invalid
3. This ensures data integrity: invalid `lines_read` can't be stored
4. Write failing test first (TDD approach)

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Added `_validate_lines_read` static method to validate `lines_read` format
   - Updated `__post_init__` to call `_validate_lines_read`
   - Validation skips invalid parts (matching `_parse_line_ranges` behavior)
   - Raises `ValueError` only if no valid parts found (and not "full")
   
2. `tests/agents/test_working_memory_entry_validation_bug.py`:
   - Updated test to expect `ValueError` for invalid `lines_read`
   
3. `tests/agents/test_working_memory.py`:
   - Updated `test_memory_should_read_file_invalid_lines_read` to expect `ValueError`
   - Updated `test_memory_should_read_file_invalid_lines_read_and_invalid_line_numbers` to use valid `lines_read`
   
4. `tests/agents/test_working_memory_full_contains_bug.py`:
   - Updated `test_lines_read_full_with_other_text` to expect `ValueError`
   
5. `tests/agents/test_working_memory_invalid_lines_read_bug.py`:
   - Updated test to expect `ValueError`
   
6. `tests/agents/test_working_memory_isdigit_bug.py`:
   - Updated `test_should_read_file_with_superscript_in_lines_read` to expect `ValueError`
   
7. `tests/agents/test_working_memory_isdigit_fix.py`:
   - Updated `test_working_memory_with_superscript_in_lines_read` to expect `ValueError`

## Impact
- **Data Integrity**: Invalid `lines_read` can no longer be stored in `WorkingMemoryEntry`
- **Error Handling**: Errors are caught early with clear messages
- **Backward Compatibility**: Validation skips invalid parts (like `_parse_line_ranges`), so mixed valid/invalid `lines_read` like "10-50,0-5,60-100" is accepted (invalid part ignored)
- **Test Coverage**: All existing tests pass with updated expectations

## Verification
- All 5819 tests pass (including 45 working memory tests)
- The fix prevents silent failures in `should_read_file`
- Clear error messages help users understand what's wrong with their `lines_read` format