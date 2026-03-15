# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T00:00:00Z
## Bug Summary
The `add_recent_file` method modifies the input `WorkingMemoryEntry` object in-place by normalizing its path, violating the principle of immutability and potentially causing unexpected side effects for callers.

## Lens
**Phase 2: State & Side Effects (The Entropy Audit)** - The code accidentally mutates inputs which could break callers.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `add_recent_file` should not modify the input object | The input object's `path` field is modified in-place |
| Callers can safely reuse or inspect the entry after adding it | Callers see unexpected changes to their data |
| The method creates a copy or uses copy-on-write semantics | The method directly modifies the input |

## Root Cause
The `add_recent_file` method calls `_normalize_path(entry.path)` and then uses `replace(entry, path=normalized_path)` to create a new entry. However, the `replace` function from `dataclasses` creates a shallow copy. If the `entry` object contains mutable fields (like `key_insights` list), those mutable fields are shared between the original and the copy. More critically, the test shows that the original entry's path is being modified, suggesting either:
1. The `replace` function is not working as expected with the serialization system
2. There's some interaction with the `SerializableDataclass` base class
3. The normalization is somehow affecting the original object

## Fix Plan
1. Create a deep copy of the entry with normalized path instead of using `replace`
2. Ensure all mutable fields are properly copied
3. Add a test to verify the input object remains unchanged

## Status: IN PROGRESS