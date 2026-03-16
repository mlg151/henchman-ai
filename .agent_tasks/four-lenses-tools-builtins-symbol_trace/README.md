# Four Lenses Bug Report: src/henchman/tools/builtins/symbol_trace.py
## Date: 2025-03-16T22:00:00Z
## Bug Summary
The `_find_definitions_in_file` function incorrectly extracts signatures for decorated functions, returning the decorator line instead of the function signature line.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Decorated function definitions should show the actual function signature (e.g., `def decorated_func(x: int) -> Optional[str]:`) | Currently returns the decorator line (e.g., `@decorator`) as the signature |
| Users should see the actual function signature for understanding the interface | Users see misleading information that doesn't show the function's parameters or return type |
| The signature should help identify the function's contract | The signature fails to provide useful information about the function |

## Root Cause
The `_extract_signature` function uses `ast.unparse(node)` which returns the entire node including decorators. When it splits by newlines and looks for lines starting with "def " or "async def ", it finds the decorator line first (if decorators are on separate lines) and returns that instead of the function signature line.

Specifically, in the `_extract_signature` function:
1. `ast.unparse(node)` returns the full source including decorators
2. It splits by newlines and iterates through lines
3. It returns the FIRST line that starts with "def " or "async def "
4. However, decorators often appear on separate lines before the function definition
5. The function returns the decorator line instead of the actual function signature

## Fix Plan
Modify the `_extract_signature` function to properly handle decorated functions by:
1. Finding the actual function definition line (not decorator lines)
2. Ensuring we return the complete function signature line
3. Maintaining backward compatibility for non-decorated functions

## Status: IN PROGRESS