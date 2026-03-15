# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T02:30:00Z
## Bug Summary
The `add_recent_file` method uses `dataclasses.replace()` to create a shallow copy of the input `WorkingMemoryEntry`, but this creates shared mutable state for the `key_insights` list. If the caller modifies the `key_insights` list after calling `add_recent_file`, the stored entry's `key_insights` will also be modified.

## Lens
**Lens 2: State & Side Effects (The Entropy Audit)** - The code creates shared mutable state between the caller and the internal storage. Modifying the input object after storing it unexpectedly modifies the stored data.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `add_recent_file` should create a deep copy or immutable snapshot of the input | `add_recent_file` creates a shallow copy, sharing mutable lists |
| Modifying input object after storage should not affect stored data | Modifying `entry.key_insights` after `add_recent_file(entry)` modifies stored data |
| Internal storage should be isolated from caller modifications | Internal storage shares references with caller |

## Root Cause
The `add_recent_file` method at line 178 uses:
```python
normalized_entry = replace(entry, path=_normalize_path(entry.path))
```

`dataclasses.replace()` creates a new dataclass instance with replaced fields, but for mutable fields like `list[str]`, it copies the reference, not the contents. So `normalized_entry.key_insights` is the same list object as `entry.key_insights`.

## Fix Plan
Create a deep copy of the entry instead of using `replace()`. Since `WorkingMemoryEntry` is a dataclass, we can use `replace()` but also need to copy mutable fields:
1. Create a copy of `key_insights` list: `key_insights=list(entry.key_insights)`
2. Use `replace(entry, path=normalized_path, key_insights=key_insights_copy)`

Alternatively, use `copy.deepcopy()` for a more robust solution.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `add_recent_file` method to create a copy of `key_insights` list using `list(entry.key_insights)` to avoid sharing mutable state.
2. `tests/agents/test_working_memory.py` - Added new test `test_memory_add_file_does_not_share_mutable_state` to verify the fix and prevent regression.

## Verification
- ✅ New test `test_memory_add_file_does_not_share_mutable_state` passes
- ✅ All existing tests pass (60/60)
- ✅ Code coverage for `working_memory.py` increased to 97%
- ✅ The fix is minimal and surgical - only changes what's necessary to fix the bug
- ✅ No other functionality is affected