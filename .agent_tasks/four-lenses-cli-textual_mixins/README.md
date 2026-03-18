# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2025-03-17T23:00:00Z
## Bug Summary
The `_textual_confirm` method in `_InitMixin` creates an unhandled asyncio task in the `_callback` function, which can cause "Task was destroyed but it is pending!" warnings during shutdown and potential memory leaks.

## Lens
**Phase 3: Performance & Resource Management** - Resource leak (unhandled asyncio task) that can cause warnings and memory issues.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Async tasks should be properly managed (stored, awaited, or cancelled) | Task created with `asyncio.create_task()` but not stored anywhere |
| No warnings during normal operation or shutdown | "Task was destroyed but it is pending!" warning possible |
| Clean resource management | Potential memory leak if task holds references |

## Root Cause
In the `_callback` function within `_textual_confirm`, when removing an entry from `_confirm_futures`, the code creates an async task to acquire the lock and pop the entry: `asyncio.create_task(remove_from_dict())`. This task is not stored or awaited, so it can be garbage collected while still pending, causing warnings.

## Fix Plan
Replace `asyncio.create_task(remove_from_dict())` with `asyncio.get_running_loop().call_soon(remove_sync)` where `remove_sync` is a sync function that pops from the dictionary. Since we're already in the event loop thread (callback from Textual), we can schedule a sync function to run immediately without creating an unmanaged task.

## Status: IN PROGRESS