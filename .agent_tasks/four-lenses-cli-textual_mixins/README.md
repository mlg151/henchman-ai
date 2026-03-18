# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2026-03-18T20:00:39.420468+00:00
## Bug Summary
The `_textual_confirm` method has a race condition where the callback function can access `self._confirm_futures` after it has been cleaned up by `_cleanup_confirm_futures`, potentially causing `KeyError` or unexpected behavior during application shutdown.

## Lens
**Phase 2: State & Side Effects (The Entropy Audit)** - Shared state mutation without proper synchronization during cleanup.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Cleanup should safely cancel all pending futures without race conditions | Callback can try to pop from `_confirm_futures` dict after cleanup has removed it |
| Futures should be properly removed from dict when cancelled | Race between callback's `pop()` and cleanup's `pop()` can cause issues |
| Application shutdown should be deterministic and safe | Potential `KeyError` or unexpected state during async cleanup |

## Root Cause
The `_cleanup_confirm_futures` method iterates through the `_confirm_futures` dictionary and cancels futures, but the callback in `_textual_confirm` also tries to remove futures from the same dictionary. During shutdown, there's a race condition where:
1. Cleanup starts and gets list of keys
2. Callback runs (triggered by future cancellation or screen dismissal)
3. Callback tries to pop from dictionary that cleanup is modifying
4. Either `KeyError` or inconsistent state can occur

## Fix Plan
Add synchronization using the existing `_confirm_lock` in the cleanup method to protect dictionary access. The lock should be acquired before accessing the dictionary to ensure atomic operations.

## Status: IN PROGRESS