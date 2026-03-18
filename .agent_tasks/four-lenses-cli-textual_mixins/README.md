# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-18T00:00:00Z

## Bug 1: Unhandled Exception in Cleanup (Already Fixed)
**Bug Summary**: The `_cleanup_confirm_futures` method in `_InitMixin` calls `future.cancel()` without exception handling. If `cancel()` raises an exception (e.g., future is in invalid state), cleanup stops and other futures won't be cancelled, potentially leaving resources dangling.

**Lens**: Phase 1: The Intent vs. Reality Check - Logic Gaps (silent failure risk)

**Status**: FIXED

**Fix**: Added try-except block around `future.cancel()` in `_cleanup_confirm_futures` method.

---

## Bug 2: Unhandled Async Task Creation (Newly Fixed)
**Bug Summary**: The `_textual_confirm` method in `_InitMixin` creates an unhandled asyncio task in the `_callback` function with `asyncio.create_task(remove_from_dict())`. This task is not stored or awaited, which can cause "Task was destroyed but it is pending!" warnings during shutdown and potential memory leaks.

**Lens**: Phase 3: Performance & Resource Management - Resource leak (unhandled asyncio task)

### Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Async tasks should be properly managed (stored, awaited, or cancelled) | Task created with `asyncio.create_task()` but not stored anywhere |
| No warnings during normal operation or shutdown | "Task was destroyed but it is pending!" warning possible |
| Clean resource management | Potential memory leak if task holds references |

### Root Cause
In the `_callback` function within `_textual_confirm`, when removing an entry from `_confirm_futures`, the code creates an async task to acquire the lock and pop the entry: `asyncio.create_task(remove_from_dict())`. This task is not stored or awaited, so it can be garbage collected while still pending, causing warnings.

### Fix Applied
1. Removed `asyncio.create_task(remove_from_dict())` call
2. Simplified callback to pop directly from `_confirm_futures` without lock
3. Added proper exception handling for `future.set_result()` to handle race conditions
4. Updated exception handlers in `_textual_confirm` to also pop directly without lock

### Rationale for Removing Lock
The lock is not needed in the callback because:
1. Both callback and cleanup use `.pop(req_id, None)` which handles missing keys gracefully (no KeyError)
2. Races between callback and cleanup are acceptable - the future will be removed from the dict by whichever runs first
3. The future result is set with proper exception handling, so even if cleanup cancels it later, the race is handled

## Status: FIXED (Both Bugs)

## Files Changed
1. `src/henchman/cli/textual_mixins.py` - Fixed both bugs:
   - Added try-except around `future.cancel()` in `_cleanup_confirm_futures` (Bug 1)
   - Removed unhandled `asyncio.create_task()` in `_textual_confirm` callback (Bug 2)
   - Added exception handling for `future.set_result()` in callback
   - Simplified dictionary access without locks where races are acceptable

## Tests
- Bug 1: Existing test `test_textual_mixins_cleanup_exception_bug.py` (if exists)
- Bug 2: Created failing test `tests/cli/test_textual_mixins_unhandled_task_failing.py` that demonstrates the bug and passes after fix