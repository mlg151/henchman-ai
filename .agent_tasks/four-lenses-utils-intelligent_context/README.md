# Four Lenses Bug Report: src/henchman/utils/intelligent_context.py
## Date: 2025-03-13T14:30:00+00:00
## Bug Summary
The `IntelligentTruncator._truncate_with_marker` method has a logic error where it calculates `available_for_content = self.safety_limit - marker_tokens` but then uses `params.min_content_tokens` instead of `available_for_content` when determining the truncation limit, potentially causing content truncation to exceed the safety limit.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When truncating content with a marker, the method should ensure total tokens (content + marker) ≤ safety_limit | The method uses `min(params.min_content_tokens, available_for_content)` but if `params.min_content_tokens > available_for_content`, it will use `available_for_content` which is correct. However, there's a deeper issue: the method doesn't properly handle the case where `available_for_content <= 0` before checking `params.min_content_tokens`. |
| Content should be truncated to fit within remaining space after reserving tokens for marker | The logic calculates `available_for_content` but then uses `min(params.min_content_tokens, available_for_content)` which could still be > 0 even when `available_for_content <= 0` if the check happens in wrong order |

## Root Cause
The bug is in the `_truncate_with_marker` method at lines ~403-420. The method has this logic flow:
1. Calculate `marker_tokens = TokenCounter.count_text(params.marker)`
2. Calculate `available_for_content = self.safety_limit - marker_tokens`
3. If `available_for_content <= 0`: handle marker-only case
4. Else: use `limit = min(params.min_content_tokens, available_for_content)`

The issue is that `params.min_content_tokens` has a default value (from `TruncationParams` dataclass), and if `available_for_content` is negative or zero, the method should handle it in step 3. However, there's a risk that the check order or default values could cause incorrect behavior.

## Fix Plan
1. Add explicit check for `available_for_content <= 0` before using `params.min_content_tokens`
2. Ensure the method always respects `self.safety_limit` as the absolute maximum
3. Write a test that demonstrates the bug with edge cases (marker tokens ≥ safety_limit)

## Status: IN PROGRESS