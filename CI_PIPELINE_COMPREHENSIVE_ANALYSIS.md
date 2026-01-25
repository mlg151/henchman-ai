# CI Pipeline Analysis and Fix Plan

## Executive Summary

The CI pipeline is currently failing with **83% pass rate** (698/842 tests passing). To achieve **100% pass rate**, we need to address **94 failing tests** and **49 test errors**. The root causes are primarily **API signature mismatches** and **corrupted source files**.

## Current State Analysis

### Test Results:
- **Total Tests**: 842
- **Passing**: 698 (83%)
- **Failing**: 94 (11%) 
- **Errors**: 49 (6%)
- **Skipped**: 1
- **Success Rate**: 83%

### Critical Issues Identified:

1. **Agent Class API Mismatch** (HIGH PRIORITY):
   - Agent constructor requires `tool_registry` parameter but tests don't provide it
   - Agent calls `tool_registry.get_tool_schemas()` but method is named `get_declarations()`
   - Affects: 49 test errors + multiple failures

2. **Corrupted Source Files** (HIGH PRIORITY):
   - `src/henchman/core/agent.py` - Contains truncated output notes
   - `src/henchman/cli/repl.py` - Contains truncated output notes  
   - Both files have syntax errors preventing imports

3. **Linting Issues** (MEDIUM PRIORITY):
   - 527 ruff errors (507 auto-fixable)
   - Mostly whitespace issues (W293)

4. **Type Checking Issues** (MEDIUM PRIORITY):
   - 8 mypy errors
   - Method name mismatches and missing imports

5. **Coverage Requirements** (HIGH PRIORITY):
   - CI requires 100% coverage (GitHub Actions)
   - Script requires 99% coverage (ci.sh)
   - Current coverage unknown due to test failures

## Root Cause Analysis

The issues appear to stem from:
1. **Refactoring Inconsistency**: ToolRegistry method renamed from `get_tool_schemas()` to `get_declarations()` but Agent class wasn't updated
2. **File Corruption**: Source files contain truncated output notes from previous tool operations
3. **Test Maintenance Gap**: Tests weren't updated for new Agent constructor signature
4. **Import Chain Breakage**: Corrupted files break the entire import chain

## Fix Implementation Plan

### Phase 1: Restore Source Files (Estimated: 1 hour)
1. **Restore `agent.py` from git/backup** ✓ (PARTIALLY DONE)
   - Remove truncated output notes
   - Fix `get_tool_schemas()` → `get_declarations()` ✓
   - Ensure proper imports

2. **Restore `repl.py` from git/backup** (IN PROGRESS)
   - Remove truncated output notes
   - Fix Agent instantiation to include `tool_registry` parameter
   - Verify all imports work

3. **Fix other corrupted files**
   - Check for similar issues in other source files

### Phase 2: Fix Core Code Issues (Estimated: 2 hours)
1. **Update Agent class** ✓ (PARTIALLY DONE)
   - Fixed method name mismatch ✓
   - Need to restore full functionality

2. **Update REPL class**
   - Ensure Agent is instantiated with `tool_registry`
   - Fix any broken method calls

3. **Fix type annotations**
   - Resolve mypy errors
   - Update import statements

### Phase 3: Fix Tests (Estimated: 3-4 hours)
1. **Update test fixtures**
   - Ensure tests pass `tool_registry` to Agent constructor
   - Mock ToolRegistry where needed

2. **Fix test assertions**
   - Update for new method names
   - Adjust for API changes

3. **Run test subsets**
   - Fix tests in batches
   - Verify incremental progress

### Phase 4: Linting and Quality (Estimated: 1-2 hours)
1. **Run ruff --fix**
   - Auto-fix 507 linting issues
   - Manually fix remaining 20 issues

2. **Verify type checking**
   - Ensure mypy passes
   - Fix any remaining type issues

3. **Run full test suite**
   - Verify 100% pass rate
   - Check coverage meets 99-100%

## Success Metrics

1. **Primary Goal**: 100% test pass rate (842/842 tests passing)
2. **Secondary Goals**:
   - 0 linting errors (ruff check passes)
   - 0 type errors (mypy passes)
   - 99-100% test coverage
   - CI pipeline passes all jobs

## Risk Assessment

### High Risk:
- Some tests may have deep integration issues requiring significant refactoring
- Coverage may be difficult to achieve with current test gaps
- UI integration tests may require complex mocking setups

### Mitigation Strategies:
1. Start with unit tests, then integration tests
2. Use test isolation and mocking to fix tests incrementally
3. Consider temporarily lowering coverage threshold if needed
4. Focus on critical path tests first

## Estimated Timeline

- **Phase 1 (Source Restoration)**: 1 hour
- **Phase 2 (Core Fixes)**: 2 hours  
- **Phase 3 (Test Fixes)**: 3-4 hours
- **Phase 4 (Quality Gates)**: 1-2 hours
- **Total Estimated Effort**: 7-9 hours

## Next Immediate Actions

1. **Restore clean `agent.py` from git** ✓ (DONE)
2. **Restore clean `repl.py` from git** (IN PROGRESS)
3. **Verify basic imports work**
4. **Run subset of tests to validate fixes**
5. **Begin systematic test repair**

## Conclusion

Achieving 100% CI pass rate is feasible but requires systematic fixing of:
1. Source file corruption
2. API signature mismatches  
3. Test maintenance gaps
4. Linting and type issues

The estimated 7-9 hour effort will yield a stable, production-ready codebase with comprehensive test coverage and quality gates.
