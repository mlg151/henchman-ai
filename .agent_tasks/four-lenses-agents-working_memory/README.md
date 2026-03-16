# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-16T01:00:00Z
## Bug Summary
The `add_recent_file` method has a type safety bug where it incorrectly handles the `key_insights` field when it's a string. If `entry.key_insights` is a string (e.g., `"insight1,insight2"`), the method wraps it in a list `["insight1,insight2"]` instead of splitting it into multiple insights `["insight1", "insight2"]`. This violates the type contract that `key_insights` should be `list[str]` and can lead to incorrect behavior in `get_file_insights`.

## Lens
**Phase 1: The Intent vs. Reality Check** - Type Safety

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `entry.key_insights` is a string, it should either be rejected (raise TypeError) or properly split into a list of strings. | The method accepts a string and wraps it in a list, creating `["insight1,insight2"]` instead of `["insight1", "insight2"]`. This violates the `list[str]` type annotation and can cause downstream issues. |

## Root Cause
The `add_recent_file` method has this logic for handling `key_insights`:
```python
key_insights=(
    [entry.key_insights] if isinstance(entry.key_insights, str) else
    list(entry.key_insights) if entry.key_insights is not None else []
)
```

If `entry.key_insights` is a string like `"insight1,insight2"`, it creates `["insight1,insight2"]` (a list with one string containing commas). The `WorkingMemoryEntry` dataclass defines `key_insights: list[str] = field(default_factory=list)`, but the `__post_init__` method only validates `lines_read`, not `key_insights`.

## Fix Plan
1. Update the `__post_init__` method of `WorkingMemoryEntry` to validate that `key_insights` is a list (or convert string to list by splitting).
2. Or update `add_recent_file` to split string `key_insights` by commas (or reject strings).

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Added validation in `WorkingMemoryEntry.__post_init__` to check that `key_insights` is a list or None (lines 70-73)
   - Simplified `add_recent_file` method to remove string handling logic since strings are now rejected at construction time (line 189)

2. `tests/agents/test_working_memory_key_insights_bug.py`:
   - Updated tests to expect `TypeError` when `key_insights` is a string (tests now pass with the fix)

3. `tests/agents/test_working_memory_key_insights_bug_fixed.py`:
   - Created new test file with tests that demonstrate the fix works correctly

## Fix Details
The fix ensures type safety by:
1. Validating in `WorkingMemoryEntry.__post_init__` that `key_insights` is either `None` or a `list`
2. Raising `TypeError` with a clear message if validation fails
3. Simplifying `add_recent_file` to assume `key_insights` is already valid (either `None` or `list`)

This prevents the bug where strings would be incorrectly wrapped in lists, maintaining the type contract that `key_insights: list[str]`.