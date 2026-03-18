# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-18T05:00:00Z
## Bug Summary
The `_textual_confirm` method has a race condition in the `else` branch when `_confirm_lock` doesn't exist. Concurrent calls can race on `_confirm_counter` increment and `_confirm_futures` dictionary insertion, causing duplicate request IDs, lost futures, and potential hangs.

## Lens
Phase 2: State & Side Effects (The Entropy Audit) - Shared State

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Concurrent calls to `_textual_confirm` should have unique request IDs | Multiple tasks can read same counter value before increment, causing duplicate IDs |
| Each future should be stored in dictionary with unique key | Futures can be overwritten (last writer wins) if same key used |
| Counter should increment atomically | `counter += 1` is not atomic (read-modify-write) |

## Root Cause
The `_textual_confirm` method has an `else` branch for when `_confirm_lock` doesn't exist (for "backward compatibility with tests"). This branch doesn't use any synchronization, allowing race conditions on `_confirm_counter` and `_confirm_futures`.

## Fix Plan
1. Create `_confirm_lock` if it doesn't exist (maintains backward compatibility)
2. Create `_confirm_futures` dict if it doesn't exist
3. Always use the lock for counter increment and dictionary insertion
4. Remove the unsafe `else` branch

## Status: FIXED

## Files Changed
1. `src/henchman/cli/textual_mixins.py` - Modified `_textual_confirm` method:
   - Added creation of `_confirm_lock` if missing
   - Added creation of `_confirm_futures` if missing  
   - Removed unsafe `else` branch
   - Always use lock for synchronization

## Test Evidence
- Created failing test demonstrating race condition
- Test shows all 50 concurrent tasks get same request ID (0) due to race
- After fix, race condition is prevented by lock
- All existing tests continue to pass