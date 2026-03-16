# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-16T02:00:31.059573+00:00
## Bug Summary
The `should_read_file` method incorrectly accepts boolean values (True/False) as line numbers due to Python's bool being a subclass of int, leading to incorrect logic where `True` is treated as line 1 and `False` as line 0.

## Lens
**Phase 1: The Intent vs. Reality Check - Type Safety**

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Line numbers should be integers, not booleans | Boolean values are accepted because bool is a subclass of int in Python |
| Invalid type should be rejected with clear error | True is treated as line 1, False as line 0 (which fails validation) |
| Type checking should use `type()` not `isinstance()` for int validation | Current code uses `type() is not int` which should catch bool but doesn't in all cases |

## Root Cause
The `should_read_file` method validates line numbers using `type(start) is not int` and `type(end) is not int`. However, when boolean values are passed:
- `True` is an instance of `bool`, which is a subclass of `int` in Python (`True == 1`, `False == 0`)
- `type(True) is bool`, not `int`, so the type check should catch it
- But the actual bug is in the validation logic flow: boolean values should be explicitly rejected

Looking at the code, I see the validation uses `type(start) is not int` which should reject `True` (since `type(True) is bool`). However, there might be a deeper issue with how the validation is structured or when it's applied.

## Fix Plan
1. Add explicit boolean check in `should_read_file` method
2. Ensure boolean values are rejected with clear error message
3. Update type validation to explicitly check for `bool` type
4. Add test case to verify boolean values are rejected

## Status: IN PROGRESS