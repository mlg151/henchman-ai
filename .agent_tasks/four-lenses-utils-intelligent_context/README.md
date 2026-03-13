# Four Lenses Bug Report: src/henchman/utils/intelligent_context.py
## Date: 2025-03-13T13:15:00.000Z
## Bug Summary
The `_is_apostrophe_in_word` function incorrectly rejects valid English contraction "may've" due to overly restrictive validation for 've contractions ending with 'y'.

## Lens
**Lens 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Function should accept "may've" as valid contraction | Function rejects "may've" because it only accepts 'y' before 've if it's "they" |
| Function should accept other 'y'-ending words before 've (e.g., "may've", "day've") | Function has special-case logic that only checks for "they" |
| Contraction validation should be based on common English patterns, not hardcoded words | Logic hardcodes "hey" check for 'y' before 've |

## Root Cause
In the `'ve` (apostrophe-ve) contraction validation, when `char_before == 'y'`, the code checks `if i < 4 or text[i-3:i].lower() != "hey":` to verify it's "they've". This rejects other valid contractions like "may've", "day've", etc. The validation should accept any word ending in 'y' before 've, not just "they".

## Fix Plan
Modify the `'ve` contraction validation to accept `char_before == 'y'` without requiring it to be "they". Remove or modify the special case check for "they". Alternatively, expand the check to include other common words ending in 'y' that can contract with 've.

## Status: FIXED

## Files Changed
1. `src/henchman/utils/intelligent_context.py` - Modified the `'ve` contraction validation logic in `_is_apostrophe_in_word` method (lines 580-595). Changed from checking for "they" specifically to checking that it's not just "y've" (single letter) by requiring `i >= 2` and `text[i-2].isalpha()`.
2. `tests/utils/test_intelligent_context_mayve_bug.py` - Added new test to verify the fix.

## Fix Details
The fix replaces the hardcoded check for "they" with a more general validation:
- When `char_before == 'y'`, require `i >= 2` (at least 2 characters before apostrophe) to reject "y've"
- Also require `text[i-2].isalpha()` to ensure it's part of a multi-letter word
- This accepts "they've", "may've", "day've", etc. while rejecting "y've"

## Verification
1. The new test `test_is_apostrophe_in_word_mayve_bug` passes, confirming "may've" is now accepted.
2. All existing tests (90 tests) pass, confirming no regression.
3. Manual testing confirms "they've" still works and "y've" is still rejected.

## Lessons Learned
1. Hardcoding specific word checks (like "they") leads to false negatives for other valid cases.
2. Contraction validation should focus on linguistic patterns rather than specific words.
3. The fix maintains the goal of rejecting invalid contractions like "y've" while accepting valid ones.
4. Edge case testing is crucial for natural language processing functions.