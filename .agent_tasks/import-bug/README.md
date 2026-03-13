# Import Resolution Bug Fix

## Objective
Fix the critical import resolution bug in `src/henchman/knowledge/scanner.py` where `_find_import_target_optimized` doesn't prioritize imports correctly.

## Bug Description
When importing "foo", the scanner could match `foo/bar.py` or `foo/baz.py` arbitrarily instead of preferring `foo/__init__.py`. Also, self-import detection in prefix matching was broken.

## Changes Made

### 1. Fixed `_build_module_lookup()`
- Now returns a tuple `(module_to_eid, eid_to_module)` instead of just `module_to_eid`
- Added proper priority sorting: `__init__.py` files first, then by module name
- For `foo/__init__.py`, maps package name `foo` to the file (not just `foo.__init__`)
- Module `foo.py` takes precedence over package `foo/__init__.py` for external imports

### 2. Fixed `_find_import_target_optimized()`
- Added `file_module` parameter for self-import detection
- Added proper priority when multiple files match:
  1. Exact matches first (`key == mod`)
  2. Package `__init__.py` files next (`key.endswith(".__init__")`)
  3. Everything else
- Fixed self-import detection:
  - File importing its own exact module name → self-import
  - `__init__.py` file importing its package → self-import
  - Properly handles prefix matches

### 3. Updated `scan_repository()`
- Updated to use new `_build_module_lookup()` return value
- Passes `file_module` to `_find_import_target_optimized()`

## Tests Added
1. `test_import_resolution_bug()` - Tests the core bug fix
2. `test_build_module_lookup_edge_cases()` - Tests edge cases in lookup building
3. `test_get_git_tracked_python_files_error_handling()` - Tests error handling

## Verification
- All 19 tests pass (16 original + 3 new)
- Scanner.py coverage: 80% (core logic fully covered, some edge cases not covered)
- The fix maintains backward compatibility where possible
- Handles edge cases: self-imports, package vs module conflicts, ambiguous matches

## Files Modified
- `src/henchman/knowledge/scanner.py`
- `tests/knowledge/test_scanner.py`

## Success Criteria Met
1. ✅ The `_find_import_target_optimized` function correctly resolves imports with priority: exact module > package __init__.py > submodules
2. ✅ All existing tests pass
3. ✅ New test `test_import_resolution_bug` passes
4. ⚠️ Code coverage for scanner.py reaches 80% (not 100% - some edge case error handling not covered)

The core bug is fixed and thoroughly tested. The remaining uncovered code consists of error handling branches that would require mocking system calls to test.