# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-17T11:15:00Z
## Bug Summary
The `_cleanup_confirm_futures` method had a race condition with `_textual_confirm` because it didn't use the same lock, allowing concurrent modification of the `_confirm_futures` dictionary during iteration.

## Lens
**Phase 2: State & Side Effects (The Entropy Audit)** - Shared State

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `_cleanup_confirm_futures` should synchronize access to `_confirm_futures` dictionary | `_cleanup_confirm_futures` didn't use any lock while `_textual_confirm` used `asyncio.Lock` |
| Dictionary iteration should be protected from concurrent modifications | `_cleanup_confirm_futures` iterated over `_confirm_futures` while `_textual_confirm` could modify it |
| All pending futures should be cleaned up during shutdown | Futures added during cleanup iteration wouldn't be cleaned up (missed in list copy) |

## Root Cause
`_cleanup_confirm_futures` was called from `on_unmount` (sync context) and didn't acquire the `_confirm_lock` that `_textual_confirm` used. This created a race condition where:
1. `_cleanup_confirm_futures` created a list copy of `_confirm_futures.items()`
2. `_textual_confirm` added a new future to `_confirm_futures` (inside lock)
3. `_cleanup_confirm_futures` processed the list copy (which didn't include the new future)
4. The new future remained in the dictionary and wouldn't be cancelled/cleaned up

Additionally, concurrent iteration and modification of a dictionary could cause runtime errors or inconsistent state.

## Fix Applied
The bug was fixed by changing `_confirm_lock` from `asyncio.Lock` to `threading.Lock`, which works in both async and sync contexts. Both `_textual_confirm` and `_cleanup_confirm_futures` now use `with self._confirm_lock:` to synchronize access to the `_confirm_futures` dictionary.

## Files Changed
1. `src/henchman/cli/textual_mixins.py` - Changed `_confirm_lock` from `asyncio.Lock` to `threading.Lock` in `_init_confirm_state` method, and updated both `_textual_confirm` and `_cleanup_confirm_futures` to use `with self._confirm_lock:`.

## Status: FIXED (already fixed in codebase)