# Improvement Summary

**Date/Time**: 2024-01-18 (automated improvement cycle)

**Files Changed**:
1. `src/henchman/cli/app.py`
   - Added missing `agent_role` parameter documentation to `_run_headless()` function docstring
   - Added missing `agent_role` parameter documentation to `_run_interactive()` function docstring

**Rationale**:
The `agent_role` parameter was properly implemented in the function signatures but was missing from the docstrings. This created inconsistency between the code and its documentation. When users or developers read the docstrings, they wouldn't know about the `agent_role` parameter even though it was fully functional.

**Changes Made**:
1. **Updated `_run_headless()` docstring**: Added `agent_role: Target a specific specialist agent.` to the Args section
2. **Updated `_run_interactive()` docstring**: Added `agent_role: Target a specific specialist agent.` to the Args section
3. **Consistency**: Used the same description as `_run_textual_tui()` which already had proper documentation

**Impact**:
- Improved documentation consistency across all CLI mode functions
- Better developer experience when reading function signatures and docstrings
- No functional changes - all existing code continues to work exactly as before
- Better API documentation for users and developers

**Testing**:
- All existing tests continue to pass (20 tests in `test_app.py`)
- No breaking changes to API or functionality
- The changes are purely documentation improvements

**Next Steps**:
1. Consider adding integration tests for `agent_role` parameter across all CLI modes
2. Ensure consistent parameter documentation for other optional parameters
3. Review other functions for similar documentation gaps