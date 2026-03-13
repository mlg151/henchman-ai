# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-13T15:00:00Z
## Bug Summary
The `should_read_file` method incorrectly returns `True` for files that were previously read fully (`lines_read="full"`). When a file has been read fully, any subsequent read (even with line ranges) should return `False` since the entire file content is already in memory.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gap

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `lines_read="full"`, any subsequent `should_read_file` call should return `False` (file already read) | The method returns `True` because `LineRange.from_str("full")` returns `None`, causing the overlap check to fail |
| The system should prevent redundant file reads when entire file is already cached | Agents will waste time and tokens re-reading files that are already fully cached |

## Root Cause
The `LineRange.from_str("full")` returns `None` because "full" doesn't match the "start-end" format. The `should_read_file` method checks `if rng and rng.overlaps(...)`, which evaluates to `False` when `rng` is `None`, causing it to fall through to the `return True` case.

## Fix Plan
Modify the `should_read_file` method to handle the special case where `match.lines_read == "full"`. When a file was read fully, we should return `False` regardless of the requested line range.

## Status: IN PROGRESS