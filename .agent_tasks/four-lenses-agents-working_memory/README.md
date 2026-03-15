# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2024-03-15T18:30:00Z
## Bug Summary
The `should_read_file` method returns incorrect result when a file was read "full" but invalid line numbers are provided (e.g., start=0). It returns `False, "File already read (full)"` instead of reporting the invalid line number error.

## Lens
**Lens 1: The Intent vs. Reality Check** - Logic Gaps: The method assumes "happy path" for line number validation and doesn't handle invalid inputs correctly when combined with "full" file reads.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When invalid line numbers are provided (e.g., start=0, end=-1), the method should return `True` with an error message about invalid line numbers, regardless of whether the file was read "full". | When a file was read "full" and invalid line numbers are provided, the method returns `False, "File already read (full)"`, masking the invalid input error. This could cause callers to think the file doesn't need to be read when they actually provided invalid parameters. |

## Root Cause
The bug is in the **order of operations** in the `should_read_file` method (lines 361-509). The method:
1. First checks if the file was read "full" (lines 384-390)
2. Then validates line numbers (lines 393-408)

When both conditions occur (file read "full" AND invalid line numbers), step 1 returns early with `False`, never reaching step 2 to validate the line numbers.

## Fix Plan
Move line number validation (lines 393-408) to **BEFORE** the "full" file check (lines 384-390). Invalid inputs should be rejected immediately, before any other logic.

## Status: IN PROGRESS