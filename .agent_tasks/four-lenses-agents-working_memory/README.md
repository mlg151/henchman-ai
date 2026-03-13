# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-13T18:15:00+00:00
## Bug Summary
The `should_read_file` method incorrectly returns `False` when a file was read fully (`lines_read="full"`) but a specific line range is requested, causing the agent to skip reading needed lines.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When a file was read fully (`lines_read="full"`), any subsequent request to read any line range should return `False` (already read). | The method returns `True` for line range requests when `lines_read="full"`, causing unnecessary re-reads and potential context window waste. |
| The method should handle the special case `lines_read="full"` before attempting to parse it as a line range. | The method tries to parse "full" as a line range, fails, and falls through to returning `True`. |

## Root Cause
In the `should_read_file` method, when `match.lines_read == "full"`, the method returns `False` only when called without line range arguments (`start` or `end` is `None`). However, when line range arguments are provided, the code proceeds to try parsing "full" as a line range via `LineRange.from_str("full")`, which returns `None`. This causes the method to fall through to the final return statement, returning `True` with the reason "Cannot determine overlap - invalid lines_read format".

## Fix Plan
Add an early return after the `if match.lines_read == "full":` check to handle both cases (with and without line range arguments). The fix should return `False` for any line range request when the file was read fully.

## Status: IN PROGRESS