# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-17T06:00:00Z
## Bug Summary
The `_textual_confirm` method has a race condition where if the confirmation screen callback is invoked after the future has already been cancelled (due to an exception or app shutdown), it will attempt to call `future.set_result()` on a cancelled future, which raises `asyncio.InvalidStateError`.

## Lens
**Phase 2: State & Side Effects (The Entropy Audit)** - Shared state synchronization issue between exception handlers and callback functions.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Callback should safely handle already-cancelled futures | Callback may raise `asyncio.InvalidStateError` when trying to set result on cancelled future |
| Exception handlers and callbacks should coordinate cleanup | Race condition between exception cleanup and callback invocation |
| Futures should be in valid state when operations are performed | Futures can be cancelled while callback is still pending |

## Root Cause
The `_callback` function inside `_textual_confirm` checks `if not future.done():` before calling `future.set_result()`, but a future can be in the `CANCELLED` state without being `done()`. In asyncio, `cancelled()` is a separate state from `done()`. When `future.cancel()` is called in the exception handlers, the future transitions to cancelled state but `future.done()` may still return `False` initially. The callback then tries to `set_result()` on a cancelled future, which raises `asyncio.InvalidStateError`.

## Fix Plan
Modify the callback to check `if not future.done() and not future.cancelled():` before calling `set_result()`. This ensures we don't try to set a result on a cancelled future. Also add proper synchronization to ensure callback and exception handlers don't interfere.

## Status: IN PROGRESS