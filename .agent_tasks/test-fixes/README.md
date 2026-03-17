# Test Fixes Task

## Goal
Ensure all tests pass with 100% coverage and all linting/type checks pass.

## Current Status
- Tests: 5422 collected, running but taking long time
- Ruff: 4 issues found
- Mypy: Many type errors found

## Issues to Fix

### Ruff Issues
1. `src/henchman/agents/orchestrator_anchoring.py:88` - Unused variable `tool_calls`
2. `src/henchman/agents/working_memory.py:357,361` - Blank line contains whitespace
3. `src/henchman/cli/input_handler.py:43,95` - Undefined name `Self`

### Mypy Issues (sample)
- `src/henchman/tools/security.py` - Missing exports (PathTraversalError, sanitize_error_message, etc.)
- Various type annotation issues

## Plan
1. Fix ruff issues first
2. Fix critical mypy issues
3. Run tests to see if any are failing
4. Fix failing tests
