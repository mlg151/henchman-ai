# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-17T01:00:00Z
## Bug Summary
In `_textual_confirm` method, when an exception occurs (not CancelledError), the code sets an exception on a Future but then re-raises the original exception, leaving the Future's exception unobserved and causing "exception never retrieved" warnings.

## Lens
Lens 1: Logic Gaps - The code assumes the Future will be awaited somewhere, but after setting an exception on it and re-raising, the Future is discarded without its exception being observed.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Exceptions in confirmation dialog should be cleanly handled and reported to the user | Future exceptions are left unobserved, causing Python warnings and potential resource leaks |
| Error handling should be consistent - either return the Future's result or raise, not both | Code sets exception on Future AND re-raises, creating two error paths |
| Cleanup should be idempotent and race-condition free | Race condition between callback and exception handler could cause KeyError |

## Root Cause
In `_textual_confirm` method (lines 476-520):
1. A Future is created and stored in `self._confirm_futures[req_id]`
2. If an exception occurs (except `asyncio.CancelledError`), the code:
   - Pops the future from the dict
   - Sets a `RuntimeError("Confirmation dialog failed")` on the future
   - Re-raises the original exception
3. The future with the set exception is never awaited (it was popped and discarded)
4. Python detects an exception was set on a Future but never retrieved, causing warnings
5. Additionally, there's a race condition if the callback runs concurrently with exception handling

## Fix Plan
1. Modify the exception handling in `_textual_confirm` to either:
   - Return `await future` (letting the Future's exception propagate)
   - OR don't set exception on the Future, just handle the error cleanly
2. Make cleanup idempotent to avoid race conditions
3. Ensure only one error path (Future OR raised exception, not both)

## Status: FIXED

## Files Changed
1. `src/henchman/cli/textual_mixins.py` - Lines 499-502:
   - Changed `future.set_exception(RuntimeError(_msg))` to `future.cancel()`
   - This avoids setting an unobserved exception on the Future while still cleaning it up properly
   - The original exception is still re-raised (preserving existing error behavior)
   - Cancelling a Future that won't be awaited is cleaner than setting an exception on it

## Fix Details
The bug was in the `_textual_confirm` method's exception handler. When `push_screen` raised an exception (other than `CancelledError`), the code would:
1. Pop the Future from `_confirm_futures`
2. Call `future.set_exception(RuntimeError("Confirmation dialog failed"))`
3. Re-raise the original exception

The Future with its set exception was never awaited, causing Python's "exception never retrieved" warnings.

The fix changes line 501 from `future.set_exception(RuntimeError(_msg))` to `future.cancel()`. This:
- Still cleans up the Future (cancels it)
- Avoids setting an exception that won't be observed
- Preserves the original exception propagation behavior
- Is consistent with the `CancelledError` handler which also cancels the Future

The race condition issue (callback vs exception handler) is mitigated because:
1. If `push_screen` raises, the callback is never registered with Textual
2. Both paths (`_callback` and exception handler) use `self._confirm_futures.pop(req_id, None)` which is idempotent (won't crash if key doesn't exist)
3. Both check `if not future.done():` before acting on the Future