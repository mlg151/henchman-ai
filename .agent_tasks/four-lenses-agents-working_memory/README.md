# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T11:45:00Z
## Bug Summary
The `_parse_line_ranges` method uses regex `r'[-\u2013\u2014]'` to find dash characters, but misses mathematical minus sign `−` (U+2212) and figure dash `‒` (U+2012). When `lines_read` contains these characters (e.g., "10−20" copied from formatted text), the method fails to parse the range and returns empty list, causing `should_read_file` to report "Cannot determine - invalid lines_read format" even though the format is valid.

## Lens
Phase 1: The Intent vs. Reality Check (Logic Gaps)

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| All common dash-like characters should be recognized: hyphen `-`, en dash `–`, em dash `—`, minus sign `−`, figure dash `‒`. | Only hyphen, en dash, and em dash are recognized. |
| "10−20" (with mathematical minus) should parse as LineRange(10,20). | Returns empty list, treated as invalid format. |
| Consistent parsing regardless of which dash character is used. | Inconsistent: depends on character choice. |

## Root Cause
The regex pattern `r'[-\u2013\u2014]'` in `_parse_line_ranges` explicitly lists only three characters:
- Hyphen `-` (ASCII 45)
- En dash `–` (U+2013)  
- Em dash `—` (U+2014)

Missing:
- Figure dash `‒` (U+2012)
- Minus sign `−` (U+2212)
- Horizontal bar `―` (U+2015)
- Other dash-like Unicode characters

When the regex doesn't match, the code treats the part as a single line number, tries `int("10−20")` which raises `ValueError`, catches it, and continues (skipping the range).

## Fix Plan
1. Expand regex to include common dash characters: `r'[-\u2012\u2013\u2014\u2015\u2212]'`
   - `\u2012`: FIGURE DASH
   - `\u2013`: EN DASH  
   - `\u2014`: EM DASH
   - `\u2015`: HORIZONTAL BAR
   - `\u2212`: MINUS SIGN
2. Alternatively, use Unicode property `\p{Pd}` (Dash_Punctuation) but Python's `re` doesn't support Unicode properties by default.
3. Keep backward compatibility with existing dash characters.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Updated regex in `_parse_line_ranges` method from `r'[-\u2013\u2014]'` to `r'[-\u2012\u2013\u2014\u2015\u2212]'` to include figure dash (U+2012), horizontal bar (U+2015), and minus sign (U+2212).
2. `tests/agents/test_working_memory.py` - Added test cases for figure dash, minus sign, and horizontal bar in `test_memory_parse_line_ranges_unicode_dash_bug` test.

## Fix Details
The regex pattern in `_parse_line_ranges` method now includes:
- `-` (hyphen, ASCII 45)
- `\u2012` (figure dash)
- `\u2013` (en dash)  
- `\u2014` (em dash)
- `\u2015` (horizontal bar)
- `\u2212` (minus sign)

This ensures that common dash-like Unicode characters used in formatted text are properly recognized when parsing line range strings like "10−20" or "10‒20".