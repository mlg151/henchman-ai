# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-16T10:00:00Z
## Bug Summary
The `should_read_file` method incorrectly handles boolean values for line numbers, treating `True` and `False` as valid integers due to Python's bool subclassing of int.

## Lens
**Phase 1: The Intent vs. Reality Check** - Type Safety issue where unexpected `bool` values could crash downstream functions or cause incorrect behavior.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Line numbers should be positive integers (1-indexed) | Boolean values `True` (1) and `False` (0) pass `type()` check but are semantically wrong |
| Invalid line numbers should be rejected early with clear error messages | `True` is treated as line 1, `False` as line 0, leading to incorrect decisions |
| Type checking should distinguish between `int` and `bool` | `isinstance(start, int)` returns `True` for booleans, but `type(start) is int` is needed |

## Root Cause
The method uses `type(start) is not int` to reject non-integer values, but this doesn't properly handle the case where `start` is a boolean (`True`/`False`). Since `bool` is a subclass of `int` in Python, `isinstance(True, int)` returns `True`, but `True` should not be considered a valid line number. The current check `type(start) is not int` correctly rejects booleans, but the error message doesn't distinguish between "not an integer" and "is a boolean".

## Fix Plan
Change the type validation to explicitly reject boolean values with a clear error message. Update the validation logic in `should_read_file` to check for boolean values and provide an appropriate error message.

## Status: IN PROGRESS