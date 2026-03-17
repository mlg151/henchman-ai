# Four Lenses Bug Report: src/henchman/utils/compaction.py
## Date: 2024-01-15T00:00:00Z
## Bug Summary
The `_truncate_protected_zone_messages` function uses integer division to estimate token reduction from character truncation, causing systematic underestimation of tokens trimmed. This can leave the protected zone over budget even after truncation.

## Lens
Phase 1: The Intent vs. Reality Check - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When truncating tool message content to reduce tokens, the function should accurately track how many tokens were actually removed. | The function uses `trimmed_tokens = (char_diff) // CHARS_PER_TOKEN_ESTIMATE` with integer division, rounding down small character reductions to 0 tokens. Cumulative errors cause underestimation, leaving protected zone over budget. |

## Root Cause
1. Line 343: `trimmed_tokens = (len(content) - len(truncated_msg.content or "")) // CHARS_PER_TOKEN_ESTIMATE`
2. Integer division (`//`) rounds down: e.g., 3 chars trimmed // 4 = 0 tokens (should be at least 1)
3. Multiple small rounding errors accumulate across messages
4. The function thinks it trimmed fewer tokens than it actually needed to, stopping truncation prematurely
5. Result: Protected zone remains over token budget despite truncation attempts

## Fix Implemented
1. Replaced integer division with actual token counting using `TokenCounter.count_text()` on both original and truncated content
2. This provides accurate token reduction calculation instead of estimating from characters
3. Added test case `test_truncation_integer_division_bug` to verify the fix
4. The fix ensures proper tracking of tokens trimmed, preventing underestimation

## Files Changed
1. `src/henchman/utils/compaction.py`:
   - Added `import math` (initially used `math.ceil()`, later replaced with better solution)
   - Replaced `trimmed_tokens = (len(content) - len(truncated_msg.content or "")) // CHARS_PER_TOKEN_ESTIMATE` with actual token counting using `TokenCounter.count_text()`
2. `tests/utils/test_compaction_edge_cases.py`:
   - Updated `test_truncation_integer_division_bug` to properly test the fix with a scenario that forces truncation

## Status: FIXED