# Test Coverage Improvement Task

**Goal**: Achieve 100% test coverage across all source files in the codebase.

**Current Status**: In progress
**Start Date**: $(date)
**Target**: 100% coverage (0 missing statements)

## Current Coverage Overview

Based on initial analysis:
- Total statements: 8080
- Missing statements: 5446 (26% coverage)
- Priority files with lowest coverage:
  1. `src/henchman/providers/openrouter.py` (64% - 14 lines, missing 5)
  2. `src/henchman/utils/ratelimit.py` (66% - 31 lines, missing 7)
  3. `src/henchman/cli/commands/team.py` (69% - 37 lines, missing 9)
  4. `src/henchman/cli/plugins.py` (74% - 60 lines, missing 13)
  5. `src/henchman/cli/session_manager.py` (75% - 60 lines, missing 14)
  6. `src/henchman/cli/tool_executor.py` (78% - 222 lines, missing 46)
  7. `src/henchman/cli/tool_manager.py` (78% - 28 lines, missing 4)
  8. `src/henchman/cli/textual_app.py` (80% - 595 lines, missing 90)

## Progress Tracking

### Phase 1: Fix Failing Tests ✓
- [x] Check test_repl_attribute_fix.py tests (all passing)
- [x] No hardcoded path issues found in current tests

### Phase 2: Priority File Coverage Improvement

#### 1. openrouter.py (64% → 100%) ✓
- [x] Analyze uncovered lines (lines 32-37, 46, 54)
- [x] Write comprehensive tests (11 tests created)
- [x] Verify coverage improvement (100% achieved)

#### 2. ratelimit.py (66% → 100%)
- [ ] Analyze uncovered lines
- [ ] Write comprehensive tests
- [ ] Verify coverage improvement

#### 3. team.py (69% → 100%)
- [ ] Analyze uncovered lines
- [ ] Write comprehensive tests
- [ ] Verify coverage improvement

#### 4. plugins.py (74% → 100%)
- [ ] Analyze uncovered lines
- [ ] Write comprehensive tests
- [ ] Verify coverage improvement

#### 5. session_manager.py (75% → 100%)
- [ ] Analyze uncovered lines
- [ ] Write comprehensive tests
- [ ] Verify coverage improvement

#### 6. tool_executor.py (78% → 100%)
- [ ] Analyze uncovered lines
- [ ] Write comprehensive tests
- [ ] Verify coverage improvement

#### 7. tool_manager.py (78% → 100%)
- [ ] Analyze uncovered lines
- [ ] Write comprehensive tests
- [ ] Verify coverage improvement

#### 8. textual_app.py (80% → 100%)
- [ ] Analyze uncovered lines
- [ ] Write comprehensive tests
- [ ] Verify coverage improvement

## Approach

For each file:
1. Read source code to understand functionality
2. Identify uncovered lines from coverage report
3. Write unit tests for uncovered code paths
4. Mock external dependencies appropriately
5. Run tests and verify coverage improvement
6. Document findings and any issues

## Notes

- Large files like textual_app.py (595 lines) will require significant test writing effort
- Some code may be difficult to test (async, UI components, external dependencies)
- Need to ensure tests don't break existing functionality
- Use pytest fixtures and mocks where appropriate