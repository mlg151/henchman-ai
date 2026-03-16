# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-16T14:00:00Z
## Bug Summary
The `should_read_file` method has a logic error in its validation order: when `end=-1` (meaning "read to EOF") is provided, the method incorrectly validates it as an invalid line number before converting it to `None` for internal processing.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `end=-1` is provided (valid special case meaning "read to EOF"), it should be converted to `None` after validation, not rejected as invalid. | The method returns `True` with error "Invalid line number: end must be -1 (for EOF) or positive (1-indexed), got end=-1" even though `end=-1` is explicitly allowed. |
| Line number validation should handle the special case `end=-1` correctly. | The validation logic incorrectly rejects `end=-1` because it checks `end < 1 and end != -1` which is always false when `end=-1`. |

## Root Cause
The bug is in the validation logic at lines 528-535 in `should_read_file`:
```python
if end is not None:
    if type(end) is not int:  # Use type() not isinstance() to reject bool (bool is subclass of int)
        return True, f"Invalid line number: end must be an integer, got {type(end).__name__}={end}"
    # end=-1 is allowed (means "read to EOF"), other negative values are not
    if end < 1 and end != -1:
        return True, f"Invalid line number: end must be -1 (for EOF) or positive (1-indexed), got end={end}"
```

The condition `end < 1 and end != -1` is logically correct, but the error message is wrong when `end=-1`. The error message says "end must be -1 (for EOF) or positive" but then says "got end=-1", which is contradictory.

Actually, looking more carefully: the condition `end < 1 and end != -1` means:
- If `end < 1` (negative or zero) AND `end != -1` (not the special EOF value), then it's invalid.
- If `end = -1`, then `end < 1` is True, but `end != -1` is False, so the whole condition is False, and it should NOT return an error.

Wait, let me trace through this more carefully. The actual bug might be elsewhere. Let me re-examine...

## Fix Plan
1. The validation logic is actually correct: `end=-1` passes the check because `end != -1` is False.
2. However, there might be a bug in how `end=-1` is handled AFTER validation. The code converts `end=-1` to `None` at line 540: `if end == -1: end = None`.
3. But then at line 544, there's another check: `if start is not None and end is not None and end != -1 and start > end:`.
4. After `end=-1` is converted to `None`, this check `end != -1` will be `None != -1` which is True, and `end is not None` will be False, so the whole condition should be False.
5. Actually, wait... line 544: `if start is not None and end is not None and end != -1 and start > end:`
   - If `end=-1` was converted to `None` at line 540, then `end is not None` is False, so condition short-circuits to False.
   - But what if `end=-1` and `start > -1`? The check `end != -1` would be False, so condition short-circuits to False.

Actually, I need to look at this more systematically. Let me create a test to understand the actual bug.

## Status: IN PROGRESS