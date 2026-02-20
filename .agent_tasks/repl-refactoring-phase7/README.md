# Phase 7: REPL Refactoring Completion

## Goal
Complete the REPL refactoring to achieve:
- REPL class under 400 lines (currently ~450 lines)
- All 4 components fully functional and independently testable
- 100% test coverage for all UI components
- All CI checks pass (ruff, mypy, pytest with 100% coverage, doctests)
- No regression in existing functionality (31/31 REPL tests currently pass)

## Current Status
**Created**: Task breakdown with 7 small, actionable tasks for engineer delegation
**Next Step**: Engineer to implement tasks sequentially

## Task Breakdown Created
Created `TASK_BREAKDOWN.md` with 7 sequential tasks:

1. **Fix Test Fixture Mocking** (0.5 days) - Update test fixtures to mock `PromptSession` instead of `henchman.cli.input.create_session`
2. **Complete ToolExecutor Integration** (1 day) - Finish ToolExecutor class and fix session manager reference sharing
3. **Reduce REPL to Under 400 Lines** (0.5 days) - Remove duplicate code and delegate remaining logic to components
4. **Create Component-Specific Tests** (1.5 days) - Add independent unit tests for each component class
5. **Add Integration Tests for Component Coordination** (1 day) - Verify components work together correctly
6. **Run Full CI Suite and Fix Issues** (0.5 days) - Ensure all CI checks pass
7. **Update Documentation and Final Review** (0.5 days) - Update architecture documentation

## Dependencies
Tasks must be completed in order due to dependencies:
1. Task 1 → Task 2 (need working tests to verify ToolExecutor)
2. Task 2 → Task 3 (need complete ToolExecutor to reduce REPL size)
3. Tasks 1-3 → Task 4 (need stable components to test)
4. Tasks 1-4 → Task 5 (need components and their tests for integration)
5. Tasks 1-5 → Task 6 (need all code changes to run CI)
6. Tasks 1-6 → Task 7 (need complete implementation to document)

## Files Modified
- `.agent_tasks/repl-refactoring-phase7/TASK_BREAKDOWN.md` - Created task breakdown
- `.agent_tasks/repl-refactoring-phase7/README.md` - This file

## Next Actions
Engineer should begin with Task 1: Fix Test Fixture Mocking, following the detailed requirements in `TASK_BREAKDOWN.md`.

## Success Criteria
- [ ] REPL class under 400 lines (currently ~450)
- [ ] All 4 components fully functional
- [ ] 100% test coverage for each component
- [ ] All CI checks pass
- [ ] No regression in existing functionality
- [ ] Components independently testable
- [ ] Architecture documentation updated