# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-17T04:00:00Z
## Bug Summary
The `_textual_confirm` method uses `id(future)` as a dictionary key, which can lead to ID collisions when futures are garbage collected and memory addresses are reused, causing wrong future to be accessed or modified.

## Lens
**Phase 1: The Intent vs. Reality Check** - This is a logic gap where the code assumes `id()` provides a unique identifier that persists over time, but Python's `id()` only guarantees uniqueness among simultaneously existing objects, not over time.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `id(future)` should provide a unique identifier that can safely be used as a dictionary key for the lifetime of the confirmation process | `id()` returns memory address which can be reused after object is garbage collected, leading to potential key collisions |
| Each confirmation future should have a truly unique ID that won't conflict with other futures | If Future A is garbage collected and Future B is allocated at same memory address, they get same `id()`, causing callbacks for Future A to affect Future B |

## Root Cause
In the `_textual_confirm` method:
```python
req_id = id(future)
self._confirm_futures[req_id] = future  # type: ignore[attr-defined]

def _callback(result: object | None) -> None:
    if not future.done():
        future.set_result(bool(result))
    self._confirm_futures.pop(req_id, None)  # type: ignore[attr-defined]
```

The bug is that `id(future)` is not a reliable unique identifier over time. Python's `id()` function returns the memory address of an object, which can be reused after the object is garbage collected. In a long-running application with many confirmation dialogs:
1. Future A is created, gets ID 1000 (memory address)
2. Future A completes, callback removes it from dict, future is garbage collected
3. Future B is created, gets allocated at same memory address, ID 1000
4. Late callback for Future A (race condition) tries to pop ID 1000, affecting Future B
5. Or `_cleanup_confirm_futures` might cancel Future B thinking it's Future A

## Fix Plan
Replace `id(future)` with a proper unique ID generator. Use the existing `self._confirm_counter` that's already initialized in `_init_confirm_state()` but currently unused. Increment it for each new confirmation request.

## Status: IN PROGRESS