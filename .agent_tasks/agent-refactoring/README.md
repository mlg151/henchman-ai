# Agent Refactoring Task

## Objective
Perform Extreme Programming (XP) refactoring on `src/henchman/core/agent.py` to improve code quality, maintainability, and test coverage while preserving all existing functionality.

## Current Issues Identified
1. **Long methods**: 
   - `run()`: 120+ lines
   - `_check_for_stalling()`: 73 lines  
   - `_apply_compaction_if_needed()`: 67 lines
2. **Deep nesting**: Multiple nested conditionals
3. **Duplicate code**: Significant duplication between `run()` and `continue_with_tool_results()`
4. **Magic numbers**: 
   - 85% multiplier for token limit
   - 8000 default tokens
   - `_max_stall_nudges = 2`
5. **Primitive obsession**: Could use domain types for configuration
6. **Feature envy**: Agent knows too much about compaction internals
7. **Low test coverage**: Currently 41% with only 6 basic tests

## Refactoring Plan
1. Extract constants to class-level constants
2. Extract helper methods from long methods
3. Create shared method for duplicated streaming logic
4. Reduce nesting depth
5. Add comprehensive tests to reach 100% coverage
6. Ensure all public API signatures remain unchanged

## Exit Criteria
- All existing tests pass
- 100% test coverage on agent.py
- Ruff and mypy linting pass
- No breaking changes to public API