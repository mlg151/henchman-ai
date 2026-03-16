# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-16T14:00:00Z
## Bug Summary
The `_normalize_path` function incorrectly normalizes an empty string `""` to `"."` (current directory), causing path comparison issues when empty paths are used.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| An empty file path `""` should either be rejected as invalid or normalized to itself `""`. | `_normalize_path("")` returns `"."`, which means empty paths get treated as current directory. |
| Path normalization should preserve the semantic meaning: empty path ≠ current directory. | If a `WorkingMemoryEntry` is created with `path=""`, it gets stored as `"."`. Later, `should_read_file` with `path="."` would incorrectly match. |

## Root Cause
The bug is in the `_normalize_path` function at line 34:
```python
def _normalize_path(path: str) -> str:
    return os.path.normpath(os.path.expanduser(path))
```

`os.path.normpath("")` returns `"."` (standard Python behavior). This causes empty paths to be normalized to current directory, which is semantically incorrect for file paths.

## Fix Plan
1. Modify `_normalize_path` to handle empty strings specially by returning them as-is, not normalizing to `"."`.
2. This preserves the semantic distinction between empty path and current directory.

## Fix Implemented
Modified `_normalize_path` function to check for empty string and return it as-is:
```python
def _normalize_path(path: str) -> str:
    """Normalize a file path for consistent comparison.
    
    Args:
        path: The file path to normalize.
        
    Returns:
        Normalized path string. Empty string is returned as-is.
    """
    if not path:
        return path  # Return empty string as-is
    
    # Use os.path.normpath to normalize path separators and remove . and ..
    # Also expand user home directory (~) if present
    return os.path.normpath(os.path.expanduser(path))
```

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `_normalize_path` function
2. `tests/agents/test_working_memory_empty_path_bug.py` - Added test file to demonstrate and verify the fix

## Status: FIXED