# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-16T02:00:31.059573+00:00
## Bug Summary
The `_parse_line_ranges` method incorrectly parses strings with underscores (e.g., "10_20") as valid line numbers because Python's `int()` function accepts underscores in integer literals. This leads to incorrect parsing where "10_20" is interpreted as line 1020 instead of being rejected as invalid input.

## Lens
**Phase 1: The Intent vs. Reality Check - Logic Gaps**

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Invalid line range format "10_20" should be rejected | "10_20" is parsed as line 1020 (single line) |
| Only valid dash characters should separate line numbers | Underscore is not a valid separator but is accepted |
| Invalid input should be skipped entirely | Invalid input creates incorrect LineRange objects |

## Root Cause
In the `_parse_line_ranges` method, when no dash character is found in a part (e.g., "10_20"), the code falls back to treating it as a single line number:
```python
else:
    # Single line
    try:
        line = int(part)
        if line < 1:
            continue  # Skip invalid: non-positive line number
        ranges.append(LineRange(line, line))
    except (ValueError, TypeError):
        continue  # Skip invalid: cannot parse as integer
```
Python's `int()` function accepts underscores in integer literals (e.g., `int("10_20")` returns `1020`), so "10_20" is incorrectly parsed as a valid line number 1020 instead of being rejected.

## Fix Plan
1. Add validation to reject strings containing underscores when parsing single line numbers
2. Or more generally, validate that the string contains only digits (0-9) before calling `int()`
3. Update the parsing logic to be more strict about valid formats

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Added `.isdigit()` checks for both dash-separated ranges and single line numbers to reject strings with underscores, decimal points, letters, etc. Fixed both `_parse_line_ranges` method and `LineRange.from_str` class method.
2. `tests/agents/test_working_memory.py` - Added test `test_memory_parse_line_ranges_underscore_bug` to verify the fix.

## Fix Details
The fix adds `.isdigit()` validation before calling `int()`:
- In `_parse_line_ranges` for dash-separated ranges: Check `if not start_str.isdigit() or not end_str.isdigit():`
- In `_parse_line_ranges` for single line numbers: Check `if not part.isdigit():`
- In `LineRange.from_str`: Check `if not parts[0].isdigit() or not parts[1].isdigit():`

This ensures that only strings containing only digits (0-9) are parsed as line numbers, rejecting underscores, decimal points, letters, and other invalid characters.