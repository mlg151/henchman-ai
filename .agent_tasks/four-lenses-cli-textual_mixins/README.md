# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-18T10:15:00Z
## Bug Summary
Race condition in tool confirmation future cleanup where `_cleanup_confirm_futures()` can cancel futures while they're being set by callbacks, causing `asyncio.InvalidStateError` or lost confirmations.

## Lens
Phase 2: State & Side Effects (The Entropy Audit) - Shared State mutation without proper synchronization

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Tool confirmation futures should be safely cancelled during cleanup without race conditions | Concurrent access to `_confirm_futures` dict during cleanup and callback execution can cause: 1. `asyncio.InvalidStateError` when trying to set result on already cancelled future 2. Futures being cancelled while callbacks are trying to set results 3. Lost confirmations when futures are popped from dict before callbacks can access them |

## Root Cause
The `_cleanup_confirm_futures()` method iterates over the `_confirm_futures` dict and cancels futures, while callbacks from confirmation screens may concurrently try to set results on those same futures. The cleanup uses `list(futures_dict.keys())` to avoid modification during iteration, but there's still a TOCTOU race between popping the future and cancelling it.

## Fix Plan
1. Use `asyncio.Lock` in `_cleanup_confirm_futures()` to synchronize access to the futures dict
2. Pop futures from dict under lock protection before cancelling them
3. Handle `asyncio.InvalidStateError` gracefully when cancelling futures that may have already completed

## Status: IN PROGRESS