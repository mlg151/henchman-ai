# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2024-03-15T18:30:00Z
## Bug Summary
The `add_recent_file` method crashes with `TypeError: 'NoneType' object is not iterable` when `entry.key_insights` is `None`. The method assumes `key_insights` is always a list, but it can be `None` at runtime despite type hints.

## Lens
**Lens 1: The Intent vs. Reality Check** - Type Safety: The method assumes `entry.key_insights` is always a list (per type hints), but Python doesn't enforce this at runtime. When `key_insights=None`, `list(entry.key_insights)` fails.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `add_recent_file` should handle `key_insights=None` gracefully, either by converting to empty list or raising a more informative error. | `add_recent_file` crashes with `TypeError: 'NoneType' object is not iterable` when `entry.key_insights` is `None`, breaking the entire working memory system. |

## Root Cause
The bug is in line 177 of `add_recent_file` method:
```python
key_insights=list(entry.key_insights)
```
This assumes `entry.key_insights` is iterable, but it can be `None`. While `WorkingMemoryEntry` has type hint `key_insights: list[str] = field(default_factory=list)`, Python doesn't enforce this at runtime. It's possible to create `WorkingMemoryEntry(key_insights=None)` or modify an existing entry to have `key_insights=None`.

## Fix Plan
Add a check for `None` before calling `list()`:
```python
key_insights=list(entry.key_insights) if entry.key_insights is not None else []
```
Or use a safer conversion:
```python
key_insights = entry.key_insights if entry.key_insights is not None else []
key_insights = list(key_insights)  # Create a copy
```

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Line 177: Added null check for `key_insights`
   - Changed: `key_insights=list(entry.key_insights)`
   - To: `key_insights=list(entry.key_insights) if entry.key_insights is not None else []`

## Test Added
1. `tests/agents/test_working_memory_key_insights_bug.py` - Test that demonstrates the bug and verifies the fix
   - `test_memory_add_recent_file_with_none_key_insights()` - Tests that `add_recent_file` handles `key_insights=None` gracefully
   - `test_memory_working_memory_entry_default()` - Tests default behavior of `WorkingMemoryEntry`

## Verification
- All existing tests pass (85 tests in `test_working_memory*.py`)
- New test passes, confirming the bug is fixed
- The fix is minimal and surgical: only changes the problematic line
- No other functionality is affected