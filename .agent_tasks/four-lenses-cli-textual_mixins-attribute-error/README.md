# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2024-01-15T00:00:00Z
## Bug Summary
The `_callback` function in `_textual_confirm` doesn't check if `_confirm_futures` exists before accessing it, which can cause an `AttributeError` if the callback runs after `_textual_confirm` has been cleaned up or if initialization failed.

## Lens
**Phase 1: Logic Gaps** - Missing null/attribute checks for shared state

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Callback should check if `_confirm_futures` exists before accessing it | Callback assumes `_confirm_futures` always exists, leading to `AttributeError` |
| Graceful handling of partially initialized or cleaned-up state | Crash when accessing non-existent attribute |
| Robust error handling for edge cases | Unhandled exception in callback |

## Root Cause
The `_callback` function defined inside `_textual_confirm` captures `self` from the outer scope and accesses `self._confirm_futures` without checking if the attribute exists. If `_textual_confirm` is called before `_init_confirm_state` (which initializes `_confirm_futures`), or if there's an initialization error, or if the callback runs after cleanup, `self._confirm_futures` won't exist, causing an `AttributeError`.

## Fix Plan
Add a check `if hasattr(self, '_confirm_futures'):` before accessing `self._confirm_futures` in the `_callback` function, similar to how the code already checks `if hasattr(self, '_confirm_lock'):`.

## Status: FIXED

## Files Changed
1. `src/henchman/cli/textual_mixins.py` - Fixed AttributeError bug in `_textual_confirm` method by adding `hasattr(self, '_confirm_futures')` checks before accessing `self._confirm_futures` in:
   - The main execution path (storing future in dict)
   - The `_callback` function  
   - The `except asyncio.CancelledError:` exception handler
   - The `except Exception:` exception handler

## Verification
- Test `test_callback_attribute_error_when_no_confirm_futures` passes (verifies fix works)
- Test output shows "GOOD: Callback checks if _confirm_futures exists"
- All existing tests continue to pass (except one test with NameError unrelated to fix)
- The fix follows the same pattern already used for checking `hasattr(self, '_confirm_lock')`