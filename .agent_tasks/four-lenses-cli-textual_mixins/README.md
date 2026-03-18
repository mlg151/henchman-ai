# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-18T16:30:00+00:00
## Bug Summary
The `_cleanup_confirm_futures` method has a race condition where it cancels futures while their callbacks might be concurrently trying to set results, causing lost confirmations and potential InvalidStateError exceptions.

## Lens
Phase 2: State & Side Effects (The Entropy Audit) - Shared State race condition

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Cleanup should safely cancel pending confirmations without interfering with in-progress callbacks | Callbacks may try to set results on futures that are being cancelled, causing InvalidStateError (suppressed) and lost confirmations |
| App shutdown should gracefully handle pending confirmations | Race between cleanup and callback execution can leave futures in inconsistent states |
| Each confirmation request should get a definitive result (True/False) | Some confirmations may be lost (future cancelled instead of getting result) |

## Root Cause
The `_cleanup_confirm_futures` method is called during app shutdown (on_unmount) and cancels all pending confirmation futures. However, these futures may have callbacks that are still executing (e.g., user clicks OK on modal dialog while app is shutting down). The callback uses `contextlib.suppress(asyncio.InvalidStateError)` to handle this race, but the suppression hides the error and the future ends up cancelled instead of having a proper result set.

The race occurs because:
1. `_cleanup_confirm_futures` pops futures from dict and cancels them
2. Callbacks (from modal dialogs) may be concurrently trying to set results on these futures
3. If `future.cancel()` happens while `future.set_result()` is executing, we get InvalidStateError
4. The error is suppressed, but the confirmation result is lost

## Fix Plan
Modify `_cleanup_confirm_futures` to first check if futures are already done before cancelling them. If a future is already done (has result/exception), leave it alone. Only cancel futures that are still pending. This prevents the race condition and ensures completed confirmations maintain their results.

## Status: IN PROGRESS