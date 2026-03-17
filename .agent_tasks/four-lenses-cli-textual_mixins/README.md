# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-17T09:15:00Z
## Bug Summary
Race condition in `_textual_confirm` method where concurrent tool confirmation requests can get duplicate request IDs, causing one future to overwrite another in `_confirm_futures` dictionary.

## Lens
**Phase 2: State & Side Effects (The Entropy Audit)** - Shared state mutation without proper synchronization.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Each tool confirmation request gets a unique ID | Concurrent requests can read same counter value before increment |
| All confirmation futures are stored and retrievable | One future can overwrite another in dictionary |
| Callback can safely set result on its future | Callback may try to set result on cancelled future causing InvalidStateError |

## Root Cause
The `_textual_confirm` method in `_InitMixin` has three related bugs:
1. **Counter race condition**: `req_id = self._confirm_counter` followed by `self._confirm_counter += 1` is not atomic
2. **Dictionary race**: Concurrent calls can store futures with same key, overwriting each other
3. **Callback safety**: Callback doesn't check `future.cancelled()` before `set_result()`

The core issue is that `self._confirm_counter` is read and incremented without synchronization, allowing concurrent calls to get the same ID. When this happens, the second future overwrites the first in `_confirm_futures`, causing the first request to never receive a response.

## Fix Plan
1. Add `asyncio.Lock` around the counter increment and dictionary update in `_textual_confirm`
2. Update callback to check both `future.done()` and `future.cancelled()` before calling `set_result()`
3. Ensure lock is properly initialized in `_init_confirm_state`

## Status: IN PROGRESS