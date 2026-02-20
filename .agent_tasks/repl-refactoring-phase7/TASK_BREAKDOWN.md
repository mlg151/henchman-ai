# Phase 7: REPL Refactoring - Task Breakdown

## Goal
Complete the REPL refactoring to achieve:
- REPL class under 400 lines (currently ~450 lines)
- All 4 components fully functional and independently testable
- 100% test coverage for all UI components
- All CI checks pass (ruff, mypy, pytest with 100% coverage, doctests)
- No regression in existing functionality (31/31 REPL tests currently pass)

## Current Status
- **REPL size**: ~450 lines (target: <400 lines)
- **Components**: 3 of 4 integrated (InputHandler, OutputHandler, CommandProcessor complete, ToolExecutor partial)
- **Test issues**: Fixtures mock `henchman.cli.input.create_session` function, ToolExecutor integration incomplete
- **Coverage**: ToolExecutor has only 5% test coverage

## Task Breakdown

### Task 1: Fix Test Fixture Mocking
**Objective**: Update test fixtures to properly mock the new component architecture instead of internal implementation details.

**Requirements**:
1. Update `test_repl.py` fixtures to mock `PromptSession` from `prompt_toolkit` instead of `henchman.cli.input.create_session`
2. Ensure all tests use the correct mocking approach for the refactored architecture
3. Verify all 31 existing REPL tests pass with updated fixtures

**Acceptance Criteria**:
- All test fixtures use `patch("prompt_toolkit.PromptSession")` instead of `patch("henchman.cli.input.create_session")`
- No test failures due to missing `create_session` function mocks
- All 31 REPL tests pass with updated fixtures

**Done When**:
- `pytest tests/cli/test_repl.py` runs without errors
- Test coverage for REPL remains at 100%
- No regression in test functionality

**Estimated Effort**: 0.5 days

---

### Task 2: Complete ToolExecutor Integration
**Objective**: Finish integrating ToolExecutor with the REPL and fix session manager reference sharing.

**Requirements**:
1. Complete the ToolExecutor class implementation in `src/henchman/cli/tool_executor.py`
2. Ensure ToolExecutor properly uses `output_handler.session_manager` for shared session management
3. Move remaining tool-related methods from REPL to ToolExecutor:
   - `_handle_tool_confirmation()`
   - `_execute_tool_call()`
   - `_process_tool_results()`
   - `_handle_agent_stream()` (already partially moved)
4. Update REPL to delegate all tool execution to ToolExecutor

**Acceptance Criteria**:
- ToolExecutor class is complete with all necessary methods
- REPL delegates all tool execution to ToolExecutor
- Session manager references are properly shared across components
- No duplicate tool execution logic in REPL

**Done When**:
- REPL has no tool execution methods (all delegated to ToolExecutor)
- ToolExecutor handles all tool confirmation, execution, and result processing
- All existing functionality works (tested via integration tests)

**Estimated Effort**: 1 day

---

### Task 3: Reduce REPL to Under 400 Lines
**Objective**: Remove duplicate code and further delegate responsibilities to components.

**Requirements**:
1. Analyze REPL for remaining methods that can be delegated to components
2. Move any remaining input/output/command/tool logic to respective handlers
3. Ensure REPL acts only as an orchestrator coordinating components
4. Verify REPL line count is under 400 lines

**Acceptance Criteria**:
- REPL class is under 400 lines total
- REPL only contains orchestration logic (initialization, run loop, component coordination)
- All business logic is in component classes
- REPL follows single responsibility principle

**Done When**:
- `wc -l src/henchman/cli/repl.py` shows < 400 lines
- REPL methods are primarily `__init__`, `run()`, and component coordination
- All tests pass with reduced REPL

**Estimated Effort**: 0.5 days

---

### Task 4: Create Component-Specific Tests
**Objective**: Add independent unit tests for each component class.

**Requirements**:
1. Create `test_input_handler.py` with comprehensive tests for InputHandler
2. Create `test_output_handler.py` with comprehensive tests for OutputHandler  
3. Create `test_command_processor.py` with comprehensive tests for CommandProcessor
4. Create `test_tool_executor.py` with comprehensive tests for ToolExecutor
5. Achieve 100% test coverage for each component

**Acceptance Criteria**:
- Each component has its own test file in `tests/cli/`
- Test coverage for each component is 100%
- Tests verify component behavior in isolation
- Tests use proper mocking for dependencies

**Done When**:
- `pytest --cov=src/henchman/cli/input_handler.py --cov-report=term-missing` shows 100% coverage
- `pytest --cov=src/henchman/cli/output_handler.py --cov-report=term-missing` shows 100% coverage
- `pytest --cov=src/henchman/cli/command_processor.py --cov-report=term-missing` shows 100% coverage
- `pytest --cov=src/henchman/cli/tool_executor.py --cov-report=term-missing` shows 100% coverage

**Estimated Effort**: 1.5 days

---

### Task 5: Add Integration Tests for Component Coordination
**Objective**: Verify components work together correctly in the REPL orchestration.

**Requirements**:
1. Create integration tests in `test_repl_integration.py` that test:
   - REPL initialization with all components
   - Component communication and coordination
   - End-to-end REPL flow with mocked provider
   - Error handling across component boundaries
2. Test edge cases and error scenarios
3. Ensure backward compatibility with existing REPL API

**Acceptance Criteria**:
- Integration tests verify REPL orchestrates components correctly
- Tests cover component interaction scenarios
- Tests verify error propagation between components
- All integration tests pass

**Done When**:
- `pytest tests/cli/test_repl_integration.py` runs without errors
- Integration tests cover main REPL workflows
- Tests demonstrate components work together as expected

**Estimated Effort**: 1 day

---

### Task 6: Run Full CI Suite and Fix Issues
**Objective**: Ensure all CI checks pass with the refactored architecture.

**Requirements**:
1. Run full test suite: `pytest --cov --cov-report=xml --cov-report=term-missing`
2. Run type checking: `mypy src/`
3. Run linting: `ruff check src/ tests/`
4. Run formatting: `ruff format --check src/ tests/`
5. Run doctests: `pytest --doctest-modules src/`
6. Fix any issues found in CI checks

**Acceptance Criteria**:
- All CI checks pass (ruff, mypy, pytest with 100% coverage, doctests)
- No new linting or type errors introduced
- Code follows project style guidelines
- Documentation is up to date

**Done When**:
- `ruff check src/ tests/` returns no errors
- `mypy src/` returns no errors  
- `pytest --cov --cov-report=xml` shows 100% coverage for REPL and components
- `ruff format --check src/ tests/` passes
- `pytest --doctest-modules src/` passes

**Estimated Effort**: 0.5 days

---

### Task 7: Update Documentation and Final Review
**Objective**: Update architecture documentation and perform final review.

**Requirements**:
1. Update `README.md` and `docs/` with new component architecture
2. Update `.agent_tasks/ui-improvements-review/REPL_REFACTOR_SUMMARY.md` with final status
3. Create architecture diagram showing component relationships
4. Verify all original refactoring goals are met
5. Perform code review of changes

**Acceptance Criteria**:
- Documentation reflects new component architecture
- Architecture diagram shows component relationships
- All refactoring goals are documented as achieved
- Code is ready for merge

**Done When**:
- Documentation is updated with new architecture
- REPL_REFACTOR_SUMMARY.md shows all goals achieved
- Architecture diagram created in docs/
- Final code review completed

**Estimated Effort**: 0.5 days

## Dependencies
1. Task 1 → Task 2 (need working tests to verify ToolExecutor)
2. Task 2 → Task 3 (need complete ToolExecutor to reduce REPL size)
3. Tasks 1-3 → Task 4 (need stable components to test)
4. Tasks 1-4 → Task 5 (need components and their tests for integration)
5. Tasks 1-5 → Task 6 (need all code changes to run CI)
6. Tasks 1-6 → Task 7 (need complete implementation to document)

## Success Metrics
- [ ] REPL class under 400 lines (currently ~450)
- [ ] All 4 components fully functional
- [ ] 100% test coverage for each component
- [ ] All CI checks pass
- [ ] No regression in existing functionality
- [ ] Components independently testable
- [ ] Architecture documentation updated

## Risks & Mitigations
1. **Test fixture complexity**: Mocking prompt_toolkit correctly may be tricky. Mitigation: Reference existing working tests.
2. **Component coupling**: Components may become too coupled. Mitigation: Define clear interfaces between components.
3. **Coverage gaps**: New components may have coverage gaps. Mitigation: Write comprehensive tests with edge cases.
4. **Performance regression**: Additional abstraction may impact performance. Mitigation: Profile critical paths and optimize.

## Exit Criteria
Phase 7 is complete when:
1. REPL class is under 400 lines
2. All 4 components are fully integrated and tested
3. All CI checks pass (ruff, mypy, pytest with 100% coverage)
4. No regression in existing REPL functionality
5. Architecture documentation is updated