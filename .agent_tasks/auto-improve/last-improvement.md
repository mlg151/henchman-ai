# Anthropic Provider Refactoring - 2026-03-01 11:45:00

## Files Changed
- `src/henchman/providers/anthropic.py` - Complete refactoring
- `src/henchman/providers/utils.py` - Added shared utility functions

## Rationale
Refactored the Anthropic provider to address all code smells identified in the report:

### 1. **Extracted Duplicate Code**
- Created `validate_messages()` in `utils.py` to eliminate duplication with `openai_compat.py`
- Created `parse_finish_reason()` in `utils.py` with provider-specific mappings

### 2. **Introduced Parameter Objects**
- Created `EventProcessingResultParams` dataclass for `_EventProcessingResult.__init__`
- Created `AnthropicProviderConfig` dataclass for `AnthropicProvider.__init__`

### 3. **Reduced Cyclomatic Complexity**
- Extracted helper methods from `_format_messages()`:
  - `_format_system_message()` - Handle system prompt extraction
  - `_format_tool_result_message()` - Format tool result messages
  - `_format_assistant_message()` - Format assistant messages with tool calls
  - `_format_regular_message()` - Format regular user/assistant messages

### 4. **Addressed Feature Envy**
- Moved `_parse_finish_reason()` to utility function
- Made `_format_messages()` more cohesive by extracting helper methods
- Kept event handlers as methods since they need provider context

### 5. **Added Missing Type Hints**
- Added complete type annotations for all methods
- Used `typing` module imports for clarity

### 6. **Extracted Streaming Logic**
- Created `_AnthropicStreamProcessor` inner class to handle stream processing
- Reduced main class size while maintaining encapsulation

## Testing Implications
- All existing tests should continue to pass
- New utility functions in `utils.py` need unit tests
- Parameter objects maintain backward compatibility
- Extracted methods preserve original behavior