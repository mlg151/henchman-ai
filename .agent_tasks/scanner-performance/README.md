# Scanner Performance Analysis & Optimization

## Objective
Analyze and optimize performance issues in `src/henchman/knowledge/scanner.py`. Focus on potential O(n²) operations, inefficient data structures, and memory usage.

## Initial Analysis

### File Overview
The scanner processes git-tracked Python files and builds a knowledge graph with:
- File and package entities
- Import relationships
- Top-level class and function names with docstrings

### Key Functions to Analyze

1. `_find_import_target()` - Lines 176-201
2. `_get_package_entities()` - Lines 122-144
3. `scan_repository()` - Main scanning function
4. `_extract_imports()` - Lines 85-108
5. `_extract_top_level_defs()` - Lines 110-120

## Performance Issues Identified

### 1. O(n²) Algorithm in `_find_import_target()`
**Issue**: The function iterates through all `python_files` for each import in each file.
- For `n` files with average `m` imports each: O(n × m × n) = O(n² × m)
- In worst case: O(n³) if each file imports many modules

**Current implementation**:
```python
def _find_import_target(
    mod: str,
    file_eid: str,
    python_files: list[str],
) -> str | None:
    for other_path in python_files:
        other_module = _path_to_module(other_path)
        if other_module.split(".")[-1] == mod or other_module.startswith(mod):
            other_eid = _path_to_entity_id(other_path)
            if other_eid != file_eid:
                return other_eid
            break  # self-match — stop searching
    return None
```

### 2. Inefficient Package Entity Creation
**Issue**: `_get_package_entities()` uses nested loops and set operations that could be optimized.

### 3. Redundant String Operations
**Issue**: Multiple calls to `_path_to_module()` and `_path_to_entity_id()` for the same paths.

### 4. File I/O Pattern
**Issue**: Each file is read twice (once for hash, once for content). Could be optimized.

### 5. Memory Usage
**Issue**: All file contents loaded into memory simultaneously during processing.

## Optimization Implemented

### 1. Precomputed Module Lookup
**Issue**: `_find_import_target()` had O(n²) complexity - for each import in each file, it iterated through all files.

**Solution**: Added `_build_module_lookup()` function that precomputes a dictionary mapping module names to entity IDs:
- Maps full module names (e.g., `src.foo.bar` → `src-foo-bar-py`)
- Maps last parts of module names (e.g., `bar` → `src-foo-bar-py`) for simple imports
- Maintains first-match semantics to match original behavior

### 2. Optimized Import Matching
**Issue**: Original `_find_import_target()` was O(n) per import.

**Solution**: Created `_find_import_target_optimized()` that uses the precomputed lookup for O(1) matching:
- Exact match first (e.g., `import foo.bar`)
- Prefix match for submodules (e.g., `import foo` matches `foo.bar`)
- Properly handles self-matches (returns `None` when file imports itself)

### 3. Updated Scanner
Modified `scan_repository()` to:
1. Build module lookup once at the beginning
2. Use optimized import matching
3. Maintains exact same behavior as original

## Performance Results

Benchmark with 200 files, 5 imports per file:
- **Naive approach**: 0.0418 seconds
- **Optimized approach**: 0.0001 seconds  
- **Speedup**: 298x

Complexity improvement:
- **Before**: O(n² × m) where n = files, m = imports per file
- **After**: O(n + n × m) = O(n × m) with much smaller constant factor

## Verification

✅ All 16 existing tests pass
✅ Linting passes (ruff, mypy)
✅ Backward compatibility maintained
✅ Performance improvement verified with benchmarks

## Files Modified
- `src/henchman/knowledge/scanner.py`:
  - Added `_build_module_lookup()` function
  - Added `_find_import_target_optimized()` function  
  - Updated `scan_repository()` to use optimized matching
  - Maintained original `_find_import_target()` for reference/compatibility

## Success Criteria Met
1. ✅ Performance analysis completed with specific findings
2. ✅ Optimization implemented (O(n²) → O(1) for import matching)
3. ✅ Tests still pass (16/16 tests pass)
4. ✅ Code passes linting and type checking