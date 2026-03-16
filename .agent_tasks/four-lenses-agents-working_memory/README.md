# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-16T12:00:00Z
## Bug Summary
The `should_read_file` method has a critical bug where it fails to validate line numbers when only one of `start` or `end` is provided (partial range specification). This allows invalid line numbers (e.g., start=0, end=None) to pass through without proper validation, leading to incorrect "should read" decisions.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `start=0` is provided (invalid, lines are 1-indexed), method should return `True` with error about invalid line number | Method returns `True` with generic "File not fully read - partial read recorded" or similar, masking the actual error |
| When `end=0` is provided (invalid), method should validate and report error | Method doesn't validate `end` when `start=None`, allowing invalid line 0 to pass |
| Line number validation should happen BEFORE checking file read status | Line number validation happens AFTER early returns for "full" files and other checks |

## Root Cause
The `should_read_file` method has validation logic for line numbers when both `start` and `end` are provided, but this validation is incomplete:

1. **Lines 547-558**: Validates `start` and `end` when both are not None
2. **Lines 560-563**: Converts `end=-1` to `None` (for "read to EOF") AFTER validation
3. **Lines 565-567**: Validates `start > end` when both are provided

However, the validation for partial ranges (`start` only or `end` only) is missing:
- When `start` is provided but `end` is None: No validation of `start` value
- When `end` is provided but `start` is None: No validation of `end` value (except for `end=-1` special case)

This creates a logic gap where invalid line numbers can pass through undetected.

## Fix Plan
Add comprehensive line number validation for all cases:
1. Validate `start` if provided (even when `end` is None)
2. Validate `end` if provided (even when `start` is None)  
3. Ensure validation happens BEFORE any other logic (including "full file" checks)
4. Use `type(start) is not int` (not `isinstance`) to reject `bool` values

## Status: IN PROGRESS