# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2026-03-15T09:15:00+00:00
## Bug Summary
The `_parse_line_ranges` method doesn't handle Unicode dash characters (en dash '–' U+2013, em dash '—' U+2014), only ASCII hyphen '-'. This causes line range parsing to fail when the input contains Unicode dashes, returning empty list instead of parsed ranges.

## Lens
Phase 1: The Intent vs. Reality Check - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| The method should parse line ranges with various dash characters: ASCII hyphen '-', en dash '–', em dash '—'. | The method only splits on ASCII hyphen '-', causing Unicode dashes to be treated as part of the number string, leading to ValueError when converting to int. |
| "10–20" (en dash) should parse as LineRange(10, 20) | "10–20" fails to parse, returns empty list |
| "10—20" (em dash) should parse as LineRange(10, 20) | "10—20" fails to parse, returns empty list |
| "10 – 20" (space, en dash, space) should parse as LineRange(10, 20) | "10 – 20" fails to parse, returns empty list |

## Root Cause
In the `_parse_line_ranges` method (lines 304-351), the code at line 324 splits on ASCII hyphen only: `if "-" in part:`. Unicode dash characters like en dash '–' (U+2013) and em dash '—' (U+2014) are not recognized as range separators. When a part contains "10–20", the condition `"-" in "10–20"` is `False` (because "–" is not "-"), so it goes to the else branch and tries `int("10–20")`, which raises `ValueError` due to the non-ASCII character, caught and skipped.

## Fix Plan
Replace the simple `"-" in part:` check with a more robust check that recognizes Unicode dash characters. Options:
1. Use regex to match various dash characters: `re.search(r'[-\u2013\u2014]', part)`
2. Normalize Unicode dashes to ASCII hyphen before parsing
3. Check for any dash-like character in a set

We'll implement option 1: use regex to detect dash characters, then split on the first dash character found.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Added `import re` at the top of the file
   - Modified `_parse_line_ranges` method to handle Unicode dash characters (en dash '–' U+2013, em dash '—' U+2014) using regex pattern `[-\u2013\u2014]`
   - Changed from simple `"-" in part:` check to `re.search(r'[-\u2013\u2014]', part)` to detect dash characters
   - Splits on the first dash character found (handles any dash type)

2. `tests/agents/test_working_memory.py`:
   - Added test `test_memory_parse_line_ranges_unicode_dash_bug` to verify the fix
   - Test covers ASCII hyphen '-', en dash '–', em dash '—', multiple ranges with Unicode dashes, and spaces with Unicode dashes

## Verification
- All existing tests pass (62 tests)
- New test verifies Unicode dash handling works correctly
- The method now correctly parses "10–20" as LineRange(10, 20) instead of returning empty list
- The method now correctly parses "10—20" as LineRange(10, 20) instead of returning empty list
- The method now correctly parses "10 – 20" (with spaces) as LineRange(10, 20) instead of returning empty list
- ASCII hyphen '-' continues to work as before