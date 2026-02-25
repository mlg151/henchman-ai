# Improvement Summary

**Date/Time**: 2024-01-15 (automated improvement cycle)

**Files Changed**:
1. `src/henchman/core/agent.py`
   - Added usage accumulation in `_process_streaming_response` method
   - Updated return type to include usage information
   - Modified FINISHED events to include usage data (as dict when available, string otherwise for backward compatibility)
   - Updated `run` method to handle new return tuple format
   - Updated `continue_with_tool_results` method to handle new return tuple format

2. `src/henchman/api/endpoints/chat.py`
   - Added usage variable initialization
   - Updated FINISHED event handling to extract usage information from dict format
   - Removed TODO comment since usage extraction is now implemented
   - Added support for both old (string) and new (dict) FINISHED event data formats

**Rationale**:
Fixed the TODO comment in the API endpoint: "Extract usage information from events". The provider implementations (e.g., OpenAICompatibleProvider) already include usage information in StreamChunk objects, but this information wasn't being passed through the agent events to the API endpoint.

**Changes Made**:
1. **Agent now captures usage information**: The `_process_streaming_response` method now accumulates usage information from StreamChunk objects.
2. **Backward-compatible event format**: FINISHED events now include usage information as a dict when available (`{"finish_reason": "...", "usage": {...}}`), but fall back to string format for backward compatibility.
3. **API endpoint extracts usage**: The chat completion endpoint now extracts usage information from FINISHED events and includes it in the response.
4. **Maintained compatibility**: All existing tests pass (except for one unrelated test failure in `test_show_team_info_prints_table` which is a mocking issue).

**Impact**:
- API clients now receive token usage information (prompt_tokens, completion_tokens, total_tokens) in chat completion responses
- No breaking changes to existing code - backward compatibility maintained
- Minimal performance impact (only accumulates usage when provided by provider)

**Testing**:
- All agent tests pass
- Type checking passes (mypy)
- The implementation handles both streaming and non-streaming responses correctly
- Usage information is optional - if providers don't include it, the API returns `null` for usage field

**Next Steps**:
This improvement completes the TODO item and provides valuable telemetry for API clients to monitor token usage and costs.