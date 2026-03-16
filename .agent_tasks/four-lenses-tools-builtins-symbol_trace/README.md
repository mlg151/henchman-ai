# Four Lenses Bug Report: src/henchman/tools/builtins/symbol_trace.py
## Date: 2025-03-16T22:00:00Z
## Bug Summary
The `_collect_annotations_from_node` function misses type annotations for positional-only arguments (`/`), `*args`, and `**kwargs` parameters, causing incomplete symbol tracing.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| All type annotations in function signatures should be collected, including those for `pos_only: int, /`, `*args: Tuple`, and `**kwargs: Dict` | Annotations for positional-only arguments, `*args`, and `**kwargs` are silently ignored |
| Complete annotation coverage for symbol tracing | Users get incomplete information about where a type is used |
| The tool should handle all Python 3.8+ syntax features | The tool fails on modern Python code with positional-only arguments |

## Root Cause
The `_collect_annotations_from_node` function only checks `args.args` (normal arguments) and `args.kwonlyargs` (keyword-only arguments), but misses:
1. `args.posonlyargs` - positional-only arguments (Python 3.8+)
2. `args.vararg` - `*args` parameter
3. `args.kwarg` - `**kwargs` parameter

These argument types can all have type annotations but are not included in the annotation collection logic.

## Fix Plan
Modify the `_collect_annotations_from_node` function to check all argument types:
1. Add `args.posonlyargs` to the loop
2. Check `args.vararg` if it exists and has an annotation
3. Check `args.kwarg` if it exists and has an annotation
4. Maintain backward compatibility

## Status: FIXED

## Files Changed
1. `src/henchman/tools/builtins/symbol_trace.py` - Modified `_collect_annotations_from_node` function to include all argument types:
   - Added check for `args.posonlyargs` (positional-only arguments)
   - Added check for `args.vararg` (`*args` parameter)
   - Added check for `args.kwarg` (`**kwargs` parameter)
2. `tests/tools/test_symbol_trace.py` - Added new test `test_finds_all_argument_type_annotations` to verify the fix

## Verification
- The failing test `test_finds_all_argument_type_annotations` now passes
- All existing tests continue to pass (33/33)
- The fix handles all Python 3.8+ syntax features for type annotations
- Complete annotation coverage for symbol tracing is now achieved