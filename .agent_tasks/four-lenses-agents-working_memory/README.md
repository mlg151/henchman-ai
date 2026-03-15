# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T01:00:00.000000+00:00
## Bug Summary
The `should_read_file` method incorrectly handles the case when `lines_read` contains Unicode whitespace (e.g., `\u2003full\u2003`). The method uses `str.strip()` which only removes ASCII whitespace, not Unicode whitespace, causing the comparison `lines_read.strip().lower() == "full"` to fail.

## Lens
Phase 1: The Intent vs. Reality Check - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `lines_read` is `"full"` with any kind of whitespace (ASCII or Unicode), the method should recognize it as "full" and return `False` (file already read fully). | When `lines_read` contains Unicode whitespace (e.g., `\u2003full\u2003`), `str.strip()` doesn't remove it, so the comparison fails. The method doesn't recognize the file as fully read, causing unnecessary re-reading. |

## Root Cause
In the `should_read_file` method, line 295: `if isinstance(lines_read, str) and lines_read.strip().lower() == "full":`. The `str.strip()` method only removes ASCII whitespace characters (space, tab, newline, etc.). Unicode whitespace characters like `\u2003` (em space), `\u00A0` (non-breaking space), etc., are not removed.

## Fix Plan
Replace `lines_read.strip().lower()` with a more robust normalization that:
1. Uses `lines_read.strip().lower()` for backward compatibility
2. OR uses a regex to remove all Unicode whitespace
3. OR uses `"".join(lines_read.split())` to remove all whitespace

The simplest fix is to use `"".join(lines_read.split())` which splits on any whitespace (including Unicode) and joins without spaces, then compare to `"full"`.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Line 295: Changed from `lines_read.strip().lower()` to `"".join(lines_read.split()).lower()` to handle Unicode whitespace.
2. `tests/agents/test_working_memory.py` - Added test `test_memory_should_read_file_full_with_unicode_whitespace` to verify the fix.

## Verification
- All existing tests pass (59 tests)
- The new test `test_memory_should_read_file_full_with_unicode_whitespace` passes
- The fix handles:
  - ASCII whitespace: `" full "` → `"full"`
  - Unicode whitespace: `"\u2003full\u2003"` → `"full"`
  - Mixed whitespace: `" \u2003 full \u2003 "` → `"full"`
  - Uppercase: `"FULL"` → `"full"`
  - No whitespace: `"full"` → `"full"`