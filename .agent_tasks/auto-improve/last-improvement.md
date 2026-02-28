# Refactoring Summary for textual_widgets.py

**Date/Time**: 2026-02-28 21:15:00 UTC  
**Files Changed**: `src/henchman/cli/textual_widgets.py`  
**Rationale**: Address code smells identified in the smell report, focusing on duplicate code, type safety, and code complexity.

## Identified Issues:

1. **Duplicate Code in ToolMessage**: `_get_header_text` and `_get_render_header` are nearly identical. `_get_body_content` and `_get_expanded_content` are also very similar.
2. **Complex `ToolMessage.__init__`**: Handles special case where `thought` parameter might actually be a `tool_call` object.
3. **Type Safety Issue**: `_add_typed_message_widget` uses `# type: ignore[return-value]` to suppress type checking.
4. **Unnecessary Instance Variables**: `ThinkingMessage` has `_header_text` and `_body_text` instance variables that are only used locally.

## Refactoring Strategy:

1. **Extract Common Logic in ToolMessage**: Create shared helper methods to avoid duplication between header and body rendering methods.
2. **Simplify `ToolMessage.__init__`**: Make the API clearer or extract the special case logic into a factory method.
3. **Fix Type Safety**: Make `_create_and_add_widget` generic to avoid the type ignore.
4. **Remove Unnecessary Instance Variables**: Convert `_header_text` and `_body_text` to local variables in `ThinkingMessage._update_renderable()`.

## Testing Implications:
- All existing tests should continue to pass.
- Need to verify that the special case handling in `ToolMessage.__init__` still works correctly.
- Ensure type safety improvements don't break any functionality.