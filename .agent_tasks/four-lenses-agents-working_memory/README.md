# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T20:15:00Z
## Bug Summary
The `should_read_file` method has a bug where it doesn't validate line number parameters before checking if a file was read "full". When invalid line numbers (e.g., start=0, end=-1) are provided for a file that was read fully, it returns `False, "File already read (full)"` instead of reporting the invalid line number error.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Invalid inputs should always be reported as errors before any other logic | Invalid line numbers are masked by "full file read" logic |
| Callers should get clear feedback about invalid parameters | Callers might think they provided valid parameters but got misleading response |
| Error handling should be consistent regardless of file read status | Different code paths for "full" vs partial reads |

## Root Cause
The `should_read_file` method has this validation order:
1. First checks if file exists in recent files
2. Then checks if file was read "full" (early return with False)
3. **Only then** validates line number parameters

This means invalid line numbers (e.g., start=0, end=-1) are not validated when a file was read "full", because the method returns early at step 2.

## Fix Plan
Move line number validation to happen BEFORE checking if file was read "full". The validation should:
1. Check start/end parameters for type and value validity (positive integers, start <= end)
2. Only after validation, check file read status
3. Return appropriate error for invalid line numbers regardless of file read status

## Status: IN PROGRESS