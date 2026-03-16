# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-16T17:30:00Z
## Bug Summary
The `_validate_lines_read` method raises `ValueError` for invalid `lines_read` formats (e.g., "10-20,invalid,30-40"), but `_parse_line_ranges` handles the same input gracefully by skipping invalid parts. This inconsistency causes deserialization to fail when loading saved working memory entries with invalid `lines_read` format, breaking the load/save contract.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps between validation and parsing

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Validation and parsing should be consistent: either both reject invalid formats or both handle them gracefully | Validation rejects invalid formats while parsing handles them gracefully |
| Deserialization of saved working memory should succeed for any data that was successfully serialized | Deserialization fails with `ValueError` for entries with invalid `lines_read` format |
| The system should be robust to minor data format issues, especially when loading saved state | System crashes when loading previously saved state with format issues |

## Root Cause
1. `_validate_lines_read` (called in `WorkingMemoryEntry.__post_init__`) raises `ValueError` for any invalid part in `lines_read` string
2. `_parse_line_ranges` (used by `should_read_file`) skips invalid parts and returns valid ranges
3. When `WorkingMemoryEntry` is loaded from YAML (deserialization), `__post_init__` is called, which calls `_validate_lines_read`
4. If saved data contains invalid `lines_read` format (e.g., from old buggy code), deserialization fails
5. This breaks the load/save contract: data that was successfully saved cannot be loaded

## Fix Plan
Make `_validate_lines_read` as lenient as `_parse_line_ranges`:
1. Modify `_validate_lines_read` to skip invalid parts instead of rejecting entire string
2. Keep the same validation logic but don't raise `ValueError` for invalid parts
3. Optionally log warnings for invalid parts
4. Ensure consistency between validation and parsing

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `_validate_lines_read` method to:
   - Accept strings with "full" regardless of invalid parts (consistent with `_parse_line_ranges`)
   - Only reject strings with no valid parts and no "full"
   - Skip invalid parts instead of rejecting entire string

2. Updated test files to reflect new behavior:
   - `tests/agents/test_working_memory_deserialization_bug.py`
   - `tests/agents/test_working_memory_actual_core_bug.py`
   - `tests/agents/test_working_memory_find_bug.py`
   - `tests/agents/test_working_memory_full_contains_bug.py`
   - `tests/agents/test_working_memory_parse_bug.py`
   - `tests/agents/test_working_memory_real_bug_find.py`
   - `tests/agents/test_working_memory_validation_bug.py`
   - `tests/agents/test_working_memory_validation_bug_fix.py`

## Verification
- All 5885 tests pass
- Deserialization now works for entries with invalid `lines_read` format as long as there's at least one valid part or "full"
- Validation and parsing are now consistent
- The load/save contract is preserved