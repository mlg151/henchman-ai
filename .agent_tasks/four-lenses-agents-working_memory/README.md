# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T20:15:00Z
## Bug Summary
The `should_read_file` method incorrectly accepts boolean values (`True`/`False`) as valid line numbers because `bool` is a subclass of `int` in Python. When `start=True` is passed, it's treated as line 1, and when `end=True` is passed, it's treated as line 1, leading to incorrect behavior.

## Lens
**Phase 1: The Intent vs. Reality Check** - Type Safety

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Boolean values should be rejected as invalid line numbers | `True` is accepted as line 1 (since `True == 1`) |
| Type validation should distinguish between `int` and `bool` | `isinstance(True, int)` returns `True` in Python |
| Clear error messages for invalid parameter types | Method proceeds with boolean values, causing incorrect logic |

## Root Cause
The validation logic uses `isinstance(start, int)` which returns `True` for boolean values since `bool` is a subclass of `int` in Python. This causes `True` to be treated as line 1 and `False` as line 0 (which fails the `start < 1` check).

## Fix Plan
Change the type validation from `isinstance(start, int)` to `type(start) is int` (or `isinstance(start, int) and not isinstance(start, bool)`) to reject boolean values while still accepting integer subclasses that are actually numeric (like `numpy.int64`).

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Changed type validation from `isinstance(start, int)` to `type(start) is int` to reject boolean values (lines 393, 400)
2. `tests/agents/test_working_memory_four_lenses_real_bug.py` - Added new test `test_memory_should_read_file_boolean_line_numbers` to verify the fix

## Verification
- Test `test_memory_should_read_file_boolean_line_numbers` now passes (previously failed)
- All existing tests continue to pass (63 tests in test_working_memory.py, 658 total agent tests)
- The fix correctly rejects boolean values (`True`/`False`) as invalid line numbers while still accepting integer values