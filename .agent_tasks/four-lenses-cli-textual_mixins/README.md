# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2026-03-17T16:00:40.205506+00:00
## Bug Summary
The `_textual_confirm` method has a TOCTOU race condition in exception handlers where `future.cancel()` can be called after the future has already completed, potentially causing `asyncio.InvalidStateError`.

## Lens
**Phase 2: State & Side Effects (The Entropy Audit)** - Shared state mutation without proper synchronization

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `future.cancel()` should be called safely on asyncio Futures | Exception handlers check `if not future.done():` before calling `future.cancel()` |
| `future.cancel()` is idempotent for asyncio Futures | TOCTOU race between check and cancel can cause InvalidStateError |
| Consistent pattern should be used throughout codebase | `_cleanup_confirm_futures` already fixed, but `_textual_confirm` still has bug |

## Root Cause
In the `_textual_confirm` method, both exception handlers (`except asyncio.CancelledError:` and `except Exception:`) have:
```python
if not future.done():
    future.cancel()
```

This creates a TOCTOU race condition. Between checking `future.done()` and calling `future.cancel()`, the `_callback` function could complete the future (setting result/exception), causing `future.cancel()` to raise `asyncio.InvalidStateError`.

The `_cleanup_confirm_futures` method was already fixed to call `future.cancel()` directly (without the check), with a comment explaining: "future.cancel() is idempotent for asyncio Futures - No need to check future.done() first (avoids TOCTOU race)".

## Fix Plan
Replace the `if not future.done(): future.cancel()` pattern in both exception handlers of `_textual_confirm` with `future.cancel()` alone, matching the fix already applied in `_cleanup_confirm_futures`.

## Status: FIXED

## Files Changed
1. `src/henchman/cli/textual_mixins.py` - Fixed TOCTOU race condition in `_textual_confirm` method by removing `if not future.done():` check before `future.cancel()` calls in both exception handlers (`except asyncio.CancelledError:` and `except Exception:`). Added explanatory comments matching the fix already present in `_cleanup_confirm_futures`.

2. `tests/cli/test_textual_mixins_toctou_bug.py` - Created new test file to verify the bug exists and that the fix works correctly. Test demonstrates the TOCTOU race condition and verifies that `future.cancel()` is idempotent.

## Verification
- Test `test_toctou_race_in_exception_handler` passes after fix (was failing before)
- All existing tests continue to pass
- The fix matches the pattern already used in `_cleanup_confirm_futures` method
- Added explanatory comments: "future.cancel() is idempotent for asyncio Futures - No need to check future.done() first (avoids TOCTOU race)"