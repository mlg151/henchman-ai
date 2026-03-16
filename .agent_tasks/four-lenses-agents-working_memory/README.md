# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-16T08:30:00Z
## Bug Summary
`LineRange.from_str` only handles hyphen '-' characters, while `_parse_line_ranges` handles multiple dash characters (hyphen, en dash, em dash, minus sign, etc.). This inconsistency can cause bugs when the same line range string is parsed differently by different methods.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps and Inconsistent Validation

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Both methods should parse the same set of dash characters | `LineRange.from_str` fails on en dash/em dash/minus sign |
| Consistent behavior across the codebase | Inconsistent parsing leads to unpredictable behavior |
| Unicode dash characters should be handled uniformly | Some code paths accept them, others reject them |

## Root Cause
`LineRange.from_str` uses simple string splitting: `s.split("-")` which only splits on hyphen '-'. `_parse_line_ranges` uses regex `re.search(r'[-\u2012\u2013\u2014\u2015\u2212]', part)` to find multiple dash-like characters (hyphen, figure dash, en dash, em dash, horizontal bar, minus sign).

## Fix Plan
Make `LineRange.from_str` use the same regex-based approach as `_parse_line_ranges` to handle all dash characters consistently.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `LineRange.from_str` to use regex for dash detection (lines 220-260)
2. `tests/agents/test_working_memory_dash_inconsistency.py` - Created test file to verify the fix

## Summary
The bug was that `LineRange.from_str` and `_parse_line_ranges` handled different sets of dash characters, leading to inconsistent parsing of line range strings. This could cause bugs when the same input was processed differently depending on which method was called. The fix makes `LineRange.from_str` use the same regex pattern as `_parse_line_ranges` to handle hyphen '-', figure dash '‒' (U+2012), en dash '–' (U+2013), em dash '—' (U+2014), horizontal bar '―' (U+2015), and minus sign '−' (U+2212).