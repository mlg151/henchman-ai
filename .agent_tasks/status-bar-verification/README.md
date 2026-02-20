# Enhanced Status Bar Implementation

## Task
Enhance the status bar in the REPL interface with additional information:
- Provider name and model
- Token usage percentage with color coding
- Active tool count
- MCP connection status

## Implementation Details

### Files Modified
1. `src/henchman/cli/repl.py` - Updated `_get_toolbar_status()` method
2. `tests/cli/test_repl_toolbar.py` - Added comprehensive tests for new functionality

### Changes Made

#### 1. Enhanced `_get_toolbar_status()` method in `repl.py`:
- **Provider and Model**: Extracts provider name from class name (e.g., "DeepSeekProvider" → "DeepSeek") and gets model from `provider.default_model`
- **Token Percentage**: Calculates percentage using `TokenCounter.count_messages()` and `settings.context.max_tokens`
  - Color coding: green (<50%), yellow (50-75%), red (>75%)
  - Falls back to token count if no settings or max_tokens is 0
- **Tool Count**: Uses `tool_registry.list_tools()` to count registered tools
- **MCP Status**: Shows connected/total clients when MCP manager exists
- **Error Handling**: All components wrapped in try/except blocks for graceful degradation

#### 2. Updated tests in `test_repl_toolbar.py`:
- Added tests for all new status bar components
- Added tests for token percentage color coding
- Added tests for edge cases (no MCP manager, no settings, provider without default_model)
- Updated existing tests to verify new functionality

### Features Implemented
✅ Status bar shows provider:model (e.g., "DeepSeek:deepseek-chat")  
✅ Status bar shows token percentage with color coding (e.g., "Tokens: 45%")  
✅ Status bar shows tool count (e.g., "Tools: 12")  
✅ Status bar shows MCP status when manager exists (e.g., "MCP: 2/3")  
✅ All information updates correctly in real-time  
✅ Tests updated or added to cover new functionality  
✅ All existing tests pass  
✅ Code follows project conventions and passes linting  

### Technical Details
- Provider name extraction: `provider.__class__.__name__.replace("Provider", "")`
- Model name: `getattr(provider, "default_model", "unknown")`
- Token percentage: `(tokens / max_tokens) * 100` where `max_tokens` from `settings.context.max_tokens`
- Tool count: `len(self.tool_registry.list_tools())`
- MCP status: `sum(1 for client in mcp_manager.clients.values() if client.is_connected)` / total

### Error Handling
- Each status component is wrapped in try/except blocks
- Missing attributes handled gracefully (e.g., provider without default_model shows "unknown")
- No MCP manager → no MCP status shown
- No settings or max_tokens=0 → falls back to token count instead of percentage

### Verification
- All 40 tests in `test_repl.py` and `test_repl_toolbar.py` pass
- Code passes `ruff check` and `mypy` type checking
- Implementation follows existing code patterns and conventions