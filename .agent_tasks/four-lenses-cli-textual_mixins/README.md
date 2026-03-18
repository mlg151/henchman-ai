# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-18T18:00:00Z
## Bug Summary
The `_textual_confirm` method in `_InitMixin` has a race condition where the callback function can access `self._confirm_futures` dictionary after it has been cleaned up by `_cleanup_confirm_futures`, potentially causing `KeyError` or incorrect state.

## Lens
**Lens 2: State & Side Effects (The Entropy Audit)** - The bug involves shared mutable state (`_confirm_futures` dictionary) that can be modified concurrently by multiple async tasks without proper synchronization.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Callback safely removes future from dictionary | Race condition: callback may try to pop from dict after cleanup removed it |
| Cleanup cancels all pending futures | Cleanup may run while callback is executing, causing KeyError |
| Dictionary operations are atomic | Concurrent dict access without lock in callback path |

## Root Cause
The `_callback` function inside `_textual_confirm` uses `self._confirm_futures.pop(req_id, None)` without acquiring the `_confirm_lock`. Meanwhile, `_cleanup_confirm_futures` (called during shutdown) also accesses the same dictionary without the lock. This creates a TOCTOU (Time-Of-Check-Time-Of-Use) race condition where:
1. Callback checks if future exists
2. Cleanup runs and removes the future
3. Callback tries to pop the future → KeyError or incorrect state

## Fix Plan
Add lock acquisition in the callback path OR make the pop operation idempotent and race-safe. Since the callback runs in sync context (from screen callback) and cleanup runs in sync context (on_unmount), we need to ensure atomic access to the dictionary.

## Status: IN PROGRESS