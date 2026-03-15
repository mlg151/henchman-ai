# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-15T17:00:24.407475+00:00
## Bug Summary
The `should_read_file` method accepts non-integer line numbers (e.g., floats like `1.5`) as valid input, leading to incorrect behavior. Line numbers must be positive integers starting at 1, but the method only checks `start < 1` which doesn't catch floats like `1.5` (since `1.5 < 1` is `False`). This causes the method to incorrectly determine that a file has been read when given fractional line numbers.

## Lens
**Phase 1: The Intent vs. Reality Check** - Type Safety

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Non-integer line numbers (floats, strings, etc.) should be rejected with clear error | Floats like `1.5` are accepted and treated as valid line numbers |
| Line number validation should check for integer type, not just value range | Only checks `start < 1`, not `not isinstance(start, int)` |
| Invalid inputs should fail fast with descriptive errors | Invalid floats pass validation and cause incorrect logic flow |

## Root Cause
1. **Missing type validation**: The validation logic at lines ~378-388 only checks:
   - `start > end` (for range validity)
   - `start < 1` and `end < 1` (for positive values)
   
   But it doesn't check that `start` and `end` are actually integers. Floats like `1.5` pass the `start < 1` check (`False`) and are then used in comparisons like `start >= rng.start`.

2. **Python's loose typing**: Python allows comparison between floats and integers (`1.5 >= 1` is `True`), so the logic doesn't crash but produces incorrect results.

3. **Type hints not enforced**: The method signature has `start: int | None` but Python doesn't enforce this at runtime.

## Fix Plan
1. Add type validation to check that `start` and `end` are integers (or None)
2. Reject non-integer values with clear error messages
3. Update the validation to happen early (before any other logic)

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Added type validation for `start` and `end` parameters in `should_read_file` method
2. `tests/agents/test_working_memory_float_bug.py` - Created test file to verify the fix

## Fix Details
Added type validation to check that `start` and `end` parameters are integers (or None) before proceeding with line number validation:

```python
if start is not None:
    if not isinstance(start, int):
        return True, f"Invalid line number: start must be an integer, got {type(start).__name__}={start}"
    if start < 1:
        return True, f"Invalid line number: start must be positive (1-indexed), got start={start}"
if end is not None:
    if not isinstance(end, int):
        return True, f"Invalid line number: end must be an integer, got {type(end).__name__}={end}"
    if end < 1:
        return True, f"Invalid line number: end must be positive (1-indexed), got end={end}"
```

This prevents non-integer values (like floats `1.5`) from being accepted as valid line numbers, which could lead to incorrect behavior since line numbers must be positive integers starting at 1.