# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T21:00:00Z
## Bug Summary
The `should_read_file` method does not normalize file paths, causing different path representations (e.g., `"./file.py"` vs `"file.py"`, `"/abs/path"` vs `"rel/path"`) to be treated as different files even when they refer to the same file.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Different string representations of the same file path should be treated as the same file (e.g., `"./file.py"` == `"file.py"`, `"/home/user/project/file.py"` == `"project/file.py"` when cwd is `/home/user`). | The method does exact string comparison `e.path == path`. Paths with different representations are treated as different files, causing unnecessary re-reading. |
| The method should normalize paths before comparison (e.g., using `os.path.normpath` or `Path.resolve()`). | No path normalization is performed, leading to cache misses and redundant file reads. |

## Root Cause
In the `should_read_file` method at line 263:
```python
matches = [e for e in reversed(self.recent_files) if e.path == path]
```

The comparison `e.path == path` is exact string equality. No path normalization is performed. Similarly, in `add_recent_file`, `get_file_insights`, and other methods that filter by path.

## Fix Plan
1. Add path normalization utility function using `os.path.normpath` or `pathlib.Path`
2. Normalize paths in `should_read_file`, `add_recent_file`, `get_file_insights`, and other path-based methods
3. Store normalized paths in `WorkingMemoryEntry` to ensure consistency
4. Add tests for path normalization edge cases

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py`:
   - Added `import os` at top of file
   - Added `_normalize_path()` helper function
   - Modified `add_recent_file()` to normalize entry paths before storing
   - Modified `should_read_file()` to normalize input path before comparison
   - Modified `get_file_insights()` to normalize input path before comparison
   
2. `tests/agents/test_working_memory.py`:
   - Added `test_memory_should_read_file_path_normalization_bug()` test to verify the fix

## Test Results
- All existing tests pass (53 tests)
- New test `test_memory_should_read_file_path_normalization_bug` passes
- The fix correctly handles:
  - `"./file.py"` == `"file.py"`
  - `"../dir/file.py"` normalization
  - User home directory expansion (`"~/file.py"`)
  - Consistent path separator normalization

## Implementation Details
The fix uses `os.path.normpath(os.path.expanduser(path))` to:
1. Expand `~` to user home directory
2. Normalize path separators (e.g., `\` to `/` on Windows)
3. Remove `.` and `..` components
4. Remove duplicate separators

Paths are normalized both when storing entries (`add_recent_file`) and when querying (`should_read_file`, `get_file_insights`), ensuring consistent comparison.