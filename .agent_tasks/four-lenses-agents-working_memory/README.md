# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-13T17:15:00+00:00
## Bug Summary
The `should_read_file` method incorrectly returns `False` when called without line range parameters (`start=None` or `end=None`) for a file that was only partially read, misleadingly claiming the file was "already read" when only a subset of lines were actually read.

## Lens
**Lens 1: Logic Gaps (Intent vs. Reality)** - The code assumes that if no line range is specified, the file doesn't need to be read if it exists in recent files. However, this creates a silent failure when a file was only partially read (e.g., lines 10-50) but the user wants to read the whole file.

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `should_read_file(path)` is called without line range (meaning "read whole file"), it should return `True` if the file was only partially read (e.g., lines_read="10-50") because the whole file hasn't been read yet. | The method returns `False` with message "File already read", which is misleading and could cause the agent to skip reading important parts of a file, leading to incomplete context and potential errors in task execution. |
| The method should distinguish between "file read fully" (lines_read="full") and "file read partially" when no line range is specified. | No distinction is made - both cases return `False` with the same generic message. |

## Root Cause
In the `should_read_file` method at line 242:
```python
if start is None or end is None:
    return False, "File already read"
```

This unconditional return assumes that if no line range is specified and the file is in recent files, it doesn't need to be read. However, this doesn't account for the case where the file was only partially read (`lines_read="10-50"` or similar). The user calling `should_read_file(path)` without line range likely wants to read the entire file, which hasn't been done if only a partial range was read.

## Fix Plan
1. Modify the logic at line 242 to check if `match.lines_read == "full"` when `start is None or end is None`.
2. If the file was read fully, return `False`.
3. If the file was read partially (or has invalid `lines_read` format), return `True` because we can't guarantee the whole file was read.
4. Update the error message to be more specific about why the decision was made.

## Status: FIXED

## Files Changed
1. **src/henchman/agents/working_memory.py** (lines 242-252):
   - Modified `should_read_file` method to check `match.lines_read == "full"` before returning `False` when `start is None or end is None`.
   - Added logic to return `True` with message "File not fully read - partial read recorded" when file was partially read and no line range specified.
   - Reordered checks to handle the "full read" case first for cleaner logic flow.

2. **tests/agents/test_working_memory.py** (lines 235-245):
   - Updated `test_memory_should_read_file_no_line_range` test to expect correct behavior.
   - Changed assertion from `assert should_read is False` to `assert should_read is True` with explanatory comment.
   - Updated expected reason message check to match new behavior.

## Fix Details
The fix addresses the logic gap by distinguishing between three cases when no line range is specified:
1. **File not in recent files**: Return `True` (needs to be read)
2. **File read fully** (`lines_read="full"`): Return `False` (already read)
3. **File read partially or invalid format**: Return `True` (not fully read, needs reading)

This prevents the silent failure where a partially read file would be incorrectly marked as "already read" when the user intends to read the entire file.