# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T00:00:00Z
## Bug Summary
The `should_read_file` method fails to recognize "full" file reads when the `lines_read` field has surrounding whitespace (e.g., "FULL ", " full", " full "), causing unnecessary re-reads of files that were already fully read.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `lines_read` is "full" (case-insensitive, with optional surrounding whitespace), any subsequent read should return `False` (no need to read) | The method only checks exact match after `.lower()`, so "FULL " (with trailing space) is not recognized as "full" |
| The method should be robust to minor data formatting variations | Files marked as fully read but with whitespace in `lines_read` are unnecessarily re-read |
| User/agent convenience: forgiving of whitespace in stored data | Strict matching causes functional bugs |

## Root Cause
Line 257 in `should_read_file`: `if match.lines_read.lower() == "full":`
- Uses `.lower()` for case-insensitivity (good)
- Does `.strip()` for whitespace (missing!)
- Result: `"FULL ".lower()` gives `"full "` which does not equal `"full"`

This causes the method to proceed to `LineRange.from_str()` which fails to parse `"FULL "` as a valid range, returning `None`, which then triggers the "invalid lines_read format" path, returning `True` (need to read).

## Fix Plan
1. Change line 257 to: `if match.lines_read.strip().lower() == "full":`
2. Add `.strip()` to remove leading/trailing whitespace before comparison
3. This maintains case-insensitivity while being forgiving of whitespace

## Status: FIXED

## Files Changed
1. **src/henchman/agents/working_memory.py** (line 257):
   - Changed: `if match.lines_read.lower() == "full":`
   - To: `if match.lines_read.strip().lower() == "full":`
   - Added `.strip()` to handle whitespace around "full"

2. **tests/agents/test_working_memory.py**:
   - Added new test method: `test_memory_should_read_file_full_with_whitespace()`
   - Tests trailing space ("FULL "), leading space (" full"), both spaces (" full "), and tabs ("\\tfull\\t")
   - Verifies all whitespace variations are correctly recognized as "full"

## Verification
- All existing tests pass (46 tests)
- New test passes, confirming the fix works
- Code coverage remains at 98% for working_memory.py
- The fix is minimal and surgical, addressing exactly one bug without refactoring unrelated code

## Impact
- Prevents unnecessary file re-reads when `lines_read` contains whitespace
- Maintains backward compatibility with existing data
- Improves robustness of the working memory system
- Follows TDD methodology: failing test first, then fix, then all tests pass