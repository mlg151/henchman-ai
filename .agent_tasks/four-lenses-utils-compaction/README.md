# Four Lenses Bug Report: src/henchman/utils/compaction.py
## Date: 2024-01-15T00:00:00Z
## Bug Summary
The `_truncate_tool_message_content` function incorrectly calculates the number of characters to trim, potentially causing negative string slicing or insufficient truncation when tokens_to_trim is small relative to content length.

## Lens
Phase 1: The Intent vs. Reality Check - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When trimming tokens from tool message content, the function should correctly convert tokens to characters and ensure the truncated content is at least MIN_TRUNCATED_CONTENT characters long. | The calculation `chars_to_trim = tokens_to_trim * CHARS_PER_TOKEN_ESTIMATE` may result in `chars_to_trim < len(message.content) - MIN_TRUNCATED_CONTENT` being false when it should be true, leading to either negative slicing or insufficient truncation. |

## Root Cause
The function uses a fixed `CHARS_PER_TOKEN_ESTIMATE = 4` to convert tokens to characters, but the actual relationship varies by language and content. More critically, the condition `if chars_to_trim < len(message.content) - MIN_TRUNCATED_CONTENT:` can fail in edge cases:
1. When `tokens_to_trim` is very small, `chars_to_trim` may be less than the difference between content length and MIN_TRUNCATED_CONTENT
2. This causes the function to use the else branch (`new_content = message.content[:MIN_TRUNCATED_CONTENT] + "\n[... heavily truncated ...]"`) even when more aggressive truncation is possible
3. The else branch doesn't respect the actual `tokens_to_trim` budget, potentially leaving the protected zone over budget

## Fix Plan
1. Fix the logic in `_truncate_tool_message_content` to properly handle the token-to-character conversion and ensure the truncation respects both the MIN_TRUNCATED_CONTENT constraint and the tokens_to_trim budget
2. Add a test case that demonstrates the bug with specific token counts
3. Ensure the fix maintains backward compatibility and doesn't break existing tests

## Status: IN PROGRESS