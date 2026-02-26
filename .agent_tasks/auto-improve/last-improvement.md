# Improvement Summary

**Date/Time**: 2024-01-15 (automated improvement cycle)

**Files Changed**:
1. `src/henchman/cli/commands/builtins.py`
   - Updated `ToolsCommand.execute()` method to check for agent's tool registry when direct tool registry is not available
   - Added fallback logic: if `ctx.tool_registry` is None but `ctx.agent` exists and has a `tool_registry` attribute, use that instead
   - Removed TODO comment "Get tools from agent/registry when available" since functionality is now implemented

2. `tests/cli/test_builtins.py`
   - Added new test method `test_execute_with_agent_tool_registry()` to verify the new functionality
   - Test verifies that when agent has a tool registry but context doesn't have a direct tool registry, the command still works

**Rationale**:
Fixed the TODO comment in the tools command: "Get tools from agent/registry when available". The `/tools` command now properly handles scenarios where:
1. Tool registry is directly available in the command context (existing behavior)
2. Tool registry is attached to the agent (new behavior)
3. Neither is available (falls back to hardcoded list for backward compatibility)

This makes the command more robust and user-friendly, especially in multi-agent scenarios or when tools are registered at the agent level rather than globally.

**Changes Made**:
1. **Enhanced tool registry discovery**: Added logic to check `ctx.agent.tool_registry` when `ctx.tool_registry` is None
2. **Backward compatibility maintained**: Falls back to hardcoded tool list when no registry is found
3. **Proper attribute checking**: Uses `hasattr()` to safely check for `tool_registry` attribute on agent
4. **Test coverage added**: New test verifies the agent tool registry fallback works correctly

**Impact**:
- Users now get accurate tool listings even when tools are registered at the agent level
- Improved developer experience in multi-agent configurations
- No breaking changes to existing code
- Better error resilience (handles missing attributes gracefully)

**Testing**:
- All existing tests pass
- New test verifies agent tool registry functionality
- Type checking passes (mypy)
- The implementation handles edge cases (None values, missing attributes)

**Next Steps**:
This improvement completes the TODO item and provides better tool discovery in the CLI. Future improvements could include:
- Showing tool categories or groups in the `/tools` output
- Filtering tools by type (read/write/execute)
- Showing tool usage examples in the output