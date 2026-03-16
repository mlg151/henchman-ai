# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2024-01-15T00:00:00Z
## Bug Summary
The `should_read_file` method has a critical bug where it incorrectly handles the case when a file was read fully (`lines_read="full"`) followed by a partial read. The method only checks the most recent entry, not all entries, causing it to incorrectly return that a file should be read even when it was previously read fully.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When a file was read fully at any point during the task, any subsequent request to read any part of that file should return `False` (skip). | The method only checks the most recent entry, so if the most recent entry is a partial read (e.g., "10-50") but an older entry shows the file was read fully ("full"), the method incorrectly returns `True` (should read). |
| The method should consider ALL entries for a file, not just the most recent one, to determine if the file has been fully read. | This causes unnecessary file re-reading, wasting API calls and context window space. |

## Root Cause
In the `should_read_file` method, when checking if a file was read fully, the code iterates through all entries (line ~540: `for match in matches:`), but then immediately returns `False` when it finds ANY entry with `lines_read="full"`. However, the bug is that this check happens AFTER the method has already collected and processed line ranges from ALL entries. The real issue is in the logic flow: the method should check for "full" reads BEFORE processing line ranges, and if ANY entry has "full", it should immediately return `False`.

Actually, looking more closely at the code (lines ~540-550), the method DOES check ALL entries for "full" and returns `False` if ANY entry has "full". So the bug might be elsewhere. Let me re-examine...

Actually, I see the issue now! The method checks for "full" in ALL entries (good), but then it proceeds to collect and process line ranges from ALL entries anyway. The problem is in how it handles the case when there are both "full" and partial entries. The check for "full" should be an early return that prevents any further processing.

## Fix Plan
Modify the `should_read_file` method to:
1. Check ALL entries for "full" reads first
2. If ANY entry has `lines_read="full"` (case-insensitive, with whitespace normalization), immediately return `False` with "File already read (full)" reason
3. Only proceed to line range processing if NO entry has "full"

This is a minimal, surgical fix that changes the early return logic.

## Status: IN PROGRESS