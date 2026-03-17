# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-17T03:15:00Z
## Bug Summary
The `_textual_confirm` method in `_InitMixin` has a race condition in ID generation: `req_id = self._confirm_counter` and `self._confirm_counter += 1` are not atomic operations. Concurrent calls to `_textual_confirm` can get the same request ID, causing one future to overwrite another in the `_confirm_futures` dictionary, leading to memory leaks, KeyErrors, or wrong futures being resolved.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic gaps in concurrent execution

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Each confirmation request gets a unique ID | Concurrent requests can get duplicate IDs |
| Futures are stored and retrieved with 1:1 mapping | Future B can overwrite Future A in dictionary |
| Each future is properly cleaned up when done | Futures can be lost (never cleaned up) or wrong future gets popped |

## Root Cause
The ID generation sequence:
```python
req_id = self._confirm_counter  # type: ignore[attr-defined]
self._confirm_counter += 1  # type: ignore[attr-defined]
self._confirm_futures[req_id] = future  # type: ignore[attr-defined]
```
is not atomic. In async Python, if two tasks call `_textual_confirm` concurrently:
1. Task A reads `_confirm_counter = 0`
2. Task B reads `_confirm_counter = 0` (before Task A increments)
3. Task A increments to 1
4. Task B increments to 1  
5. Both tasks use ID 0, causing Task B's future to overwrite Task A's future

## Fix Plan
Instead of using a counter with non-atomic increment (`self._confirm_counter += 1`), use the future's unique object ID (`id(future)`) as the dictionary key. This guarantees uniqueness without race conditions or locks.

## Status: FIXED

## Files Changed
1. `src/henchman/cli/textual_mixins.py`:
   - Changed `_textual_confirm` method to use `req_id = id(future)` instead of `req_id = self._confirm_counter`
   - Removed `self._confirm_counter += 1` (counter is kept for compatibility but no longer used)
   - Removed unused `_confirm_lock` that was added initially
   
## Fix Details
The original code had a race condition:
```python
req_id = self._confirm_counter  # Read
self._confirm_counter += 1      # Increment (not atomic!)
self._confirm_futures[req_id] = future
```

Two concurrent async tasks could:
1. Both read the same counter value (e.g., 0)
2. Both increment it (to 1, then 2)  
3. Both use the same ID (0), causing one future to overwrite another

The fix uses Python's built-in `id()` function which returns a unique integer for each object's lifetime:
```python
req_id = id(future)  # Always unique for this future
self._confirm_futures[req_id] = future
```

This eliminates the race condition entirely without needing locks or atomic operations.