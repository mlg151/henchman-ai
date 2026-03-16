# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-16T10:00:00Z
## Bug Summary
The `_validate_lines_read` method in `WorkingMemoryEntry` incorrectly accepts invalid strings like `"full,invalid"` because it only checks if `"full"` is present, ignoring other invalid content. This violates the principle that validation should reject invalid input.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic gap where invalid input is silently accepted due to overly permissive validation.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Invalid `lines_read` strings should be rejected with clear error messages | `"full,invalid"` is accepted because it contains `"full"`, even though `"invalid"` is not a valid range |
| Validation should be consistent: `"invalid"` alone is rejected, but `"full,invalid"` is accepted | Inconsistent validation creates confusion and potential bugs |
| Invalid content should not be silently ignored | The `continue` statements skip invalid parts without warning, allowing garbage data |

## Root Cause
The validation logic in `_validate_lines_read` has the condition: `if not has_full and not has_valid_range and normalized:`. This means if `has_full` is `True` (string contains `"full"`), the validation passes regardless of whether there are other invalid parts. The comment says "If we have 'full', it's valid regardless of other valid ranges", but `"invalid"` is not a "range" at all - it's invalid content that should be rejected.

## Fix Plan
Change the validation logic to reject strings containing invalid non-range content even when `"full"` is present. Add a `has_invalid_part` flag that tracks whether any invalid parts were encountered during parsing. If `has_invalid_part` is `True`, raise `ValueError` regardless of whether `"full"` is present.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Updated `_validate_lines_read` method to track invalid parts and reject strings containing invalid content
2. `tests/agents/test_working_memory_full_contains_bug.py` - Updated test expectations to match new behavior (reject `"full,additional info"`)
3. `tests/agents/test_working_memory_parse_bug.py` - Updated test expectations to match new behavior (reject `"10-50,0-5,60-100"`)
4. `tests/agents/test_working_memory_validation_bug_fix.py` - Updated test expectations to match new behavior (reject `"full,invalid-format"`)
5. `tests/agents/test_working_memory_validation_bug.py` - New test created to verify the fix (expects rejection of `"full,invalid"`)

## Fix Details
The fix adds a `has_invalid_part` flag that is set to `True` when any invalid part is encountered (non-decimal characters, invalid line numbers, etc.). If `has_invalid_part` is `True`, the validation raises `ValueError` with message "Invalid lines_read '{lines_read}': contains invalid content". This ensures that strings containing any invalid content are rejected, even when `"full"` is present.