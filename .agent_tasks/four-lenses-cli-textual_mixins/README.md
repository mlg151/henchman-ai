# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2026-03-17T19:15:00+00:00
## Bug Summary
The `_textual_confirm` method has a race condition where the `_callback` function can access `self._confirm_futures` after it has been cleaned up during shutdown, potentially causing `KeyError` or `AttributeError`.

## Lens
Phase 2: State & Side Effects (The Entropy Audit) - Shared State mutation without proper synchronization during cleanup.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Callback should safely handle missing futures during cleanup | Callback assumes `_confirm_futures` dict exists and contains the key |
| Cleanup should prevent callbacks from accessing cleaned state | Callback runs asynchronously and may access dict after cleanup |
| Thread-safe access to shared mutable state | No lock protection in sync callback context |

## Root Cause
The `_callback` function is defined as a regular function (not async) and accesses `self._confirm_futures` without acquiring the lock in the sync callback context. During `_cleanup_confirm_futures()` (called from `on_unmount`), futures are cancelled and removed from the dict, but callbacks may still run and try to access the dict.

## Fix Plan
1. Add null-check in `_callback` before accessing `self._confirm_futures`
2. Use `pop()` with default value to avoid KeyError
3. Ensure callback is idempotent and handles missing futures gracefully

## Status: IN PROGRESS