# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-17T22:15:00Z
## Bug Summary
The `_textual_confirm` method uses `id(future)` as dictionary keys for tracking confirmation futures, which can lead to key collisions when memory addresses are reused after garbage collection.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Each confirmation request should have a unique identifier that persists for the lifetime of the confirmation dialog | Using `id(future)` creates identifiers that can be reused when Python recycles memory addresses |
| The system should reliably track pending confirmations and clean them up properly | Memory address reuse can cause late callbacks to affect wrong futures or cleanup to remove wrong entries |
| Concurrent confirmation requests should not interfere with each other | Key collisions could cause race conditions in the `_confirm_futures` dictionary |

## Root Cause
The code uses `id(future)` as a dictionary key in `_confirm_futures`. While `id()` returns a unique identifier for an object's lifetime, Python can and does reuse memory addresses after objects are garbage collected. If:
1. Future A is created with memory address X
2. Future A completes and is garbage collected
3. Future B is created and gets the same memory address X (memory reuse)
4. A late callback for Future A could affect Future B

The current implementation attempts to mitigate this with a counter system, but there's still a race condition in the initialization logic.

## Fix Plan
1. Ensure `_confirm_counter` is always used instead of `id(future)` 
2. Make the counter increment atomic with proper locking
3. Verify all code paths use the counter-based approach consistently
4. Add a test that demonstrates the bug and verifies the fix

## Status: IN PROGRESS