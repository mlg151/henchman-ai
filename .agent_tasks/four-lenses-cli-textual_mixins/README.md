# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2026-03-18T20:00:39.420468+00:00
## Bug Summary
The `_cleanup_confirm_futures` method cannot synchronize with `_textual_confirm` because it's called from synchronous `on_unmount` context but tries to coordinate with an `asyncio.Lock`. This creates a race condition where cleanup can modify `_confirm_futures` dictionary while `_textual_confirm` is concurrently accessing it.

## Lens
**Phase 2: State & Side Effects (The Entropy Audit)** - Shared state mutation without proper synchronization due to async/sync context mismatch.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Synchronization should work in both async and sync contexts | `_cleanup_confirm_futures` can't acquire `asyncio.Lock` in sync context |
| State modifications should be atomic and race-free | Cleanup can modify dictionary while `_textual_confirm` holds the lock |
| Shutdown should be deterministic and safe | Potential dictionary corruption or inconsistent state during concurrent access |

## Root Cause
`_textual_confirm` uses `asyncio.Lock` for synchronization (appropriate for async context), but `_cleanup_confirm_futures` is called from `on_unmount` which is synchronous. The cleanup method cannot acquire the async lock, so it operates without synchronization, creating a race condition with concurrent `_textual_confirm` operations.

## Fix Plan
Replace `asyncio.Lock` with `threading.Lock` (or a reentrant lock) that works in both async and sync contexts. This allows `_cleanup_confirm_futures` to properly synchronize with `_textual_confirm`.

## Status: IN PROGRESS