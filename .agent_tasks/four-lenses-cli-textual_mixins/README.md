# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-18T03:00:00Z
## Bug Summary
The `_textual_confirm` method in `_InitMixin` has a race condition where the `_confirm_futures` dictionary can be accessed concurrently without proper synchronization, potentially causing `KeyError` or incorrect future resolution.

## Lens
**Phase 2: State & Side Effects (The Entropy Audit)** - Shared State race condition

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Concurrent access to `_confirm_futures` dictionary should be thread-safe | Multiple async tasks can modify `_confirm_futures` simultaneously causing `KeyError` or lost futures |
| Future callbacks should always find their future in the dictionary | Callback may try to `.pop()` a future that was already removed by cleanup |
| Lock should protect all dictionary operations | Lock is only used for counter increment, not for dictionary access |

## Root Cause
The `_textual_confirm` method uses an `asyncio.Lock` to protect the counter increment (`req_id = self._confirm_counter; self._confirm_counter += 1`) but does not use the lock to protect access to the `_confirm_futures` dictionary. The callback function `_callback` and the cleanup method `_cleanup_confirm_futures` both access the dictionary without synchronization, creating race conditions.

Additionally, the callback uses `.pop(req_id, None)` which is not atomic with respect to the lock, and cleanup iterates over dictionary keys while potentially modifying it.

## Fix Plan
1. Use the existing `_confirm_lock` to protect ALL access to `_confirm_futures` dictionary
2. Make the callback acquire the lock before accessing the dictionary
3. Make cleanup acquire the lock before iterating over futures
4. Ensure atomic operations within lock context

## Status: IN PROGRESS