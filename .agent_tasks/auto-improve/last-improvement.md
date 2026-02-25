# Auto-Improvement Summary

## Date/Time
2025-02-25

## Files Changed
1. `src/henchman/providers/base.py` - Added `usage` field to `StreamChunk` dataclass
2. `src/henchman/providers/openai_compat.py` - Added usage extraction from OpenAI API responses

## Improvement Made
Added token usage tracking to the OpenAI-compatible provider by:
1. Extending the `StreamChunk` dataclass with an optional `usage` field to store token usage information (prompt_tokens, completion_tokens, total_tokens)
2. Modifying the `OpenAICompatibleProvider` to extract usage information from OpenAI API responses and include it in `StreamChunk` objects

## Problem
The chat completion API endpoint had a TODO comment: "Extract usage information from events". However, the underlying `StreamChunk` objects didn't have a field to store usage information, and providers weren't extracting it from API responses.

## Solution
1. Added `usage: dict[str, int] | None = None` field to the `StreamChunk` dataclass in `base.py`
2. Updated `OpenAICompatibleProvider.chat_completion_stream()` to extract usage information from OpenAI API chunks when available
3. The usage is extracted as a dictionary with keys: `prompt_tokens`, `completion_tokens`, and `total_tokens`

## Changes
1. **StreamChunk enhancement** (base.py):
   - Added `usage` field with type `dict[str, int] | None = None`
   - Added documentation comment explaining the field contains token usage information

2. **OpenAICompatibleProvider update** (openai_compat.py):
   - Added code to check if chunk has `usage` attribute and extract token counts
   - Converts OpenAI's `CompletionUsage` object to a dictionary
   - Includes usage in yielded `StreamChunk` objects

## Rationale
This improvement:
- Provides the foundation for token usage tracking across all providers
- Enables future work to pass usage information through the agent system to API endpoints
- Follows the OpenAI API standard for usage reporting
- Is backward compatible (optional field with default `None`)
- Sets up the infrastructure needed to address the TODO in the chat endpoint

## Testing
- Ran existing provider tests: `python -m pytest tests/providers/test_base.py -xvs`
- Ran OpenAI provider tests: `python -m pytest tests/providers/test_openai_compat.py -xvs -k "stream"`
- All tests pass successfully
- No breaking changes to existing functionality

## Impact
- Small, focused improvement that adds valuable infrastructure
- Enables token usage tracking for OpenAI-compatible providers
- Prepares for completing the TODO in the chat endpoint
- Minimal code change (6 lines added across 2 files)
- Backward compatible - doesn't break existing code