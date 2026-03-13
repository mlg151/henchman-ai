# IntelligentContextManager Refactoring Test Plan

## Current Issues Identified (from smell report):

1. **Large Class** (779 lines, 29 methods)
2. **Primitive Obsession** in `__init__` (5 primitive parameters)
3. **Duplicate Code**: `_sort_messages_by_importance` vs `_sort_clusters_by_importance`
4. **Feature Envy**: Multiple methods accessing other objects more than `self`
5. **Long Methods**: `_apply_intelligent_truncation` (33+ lines), `compact_with_result` (40+ lines)

## Refactoring Strategy:

### Phase 1: Fix Primitive Obsession
- Add alternative constructor that accepts `IntelligentContextConfig` object
- Keep backward compatibility with existing parameter-based constructor
- Update tests to use config object where possible

### Phase 2: Extract Helper Classes
1. **MessageSafetyEnforcer** - for `_enforce_message_safety_limit`, `_create_truncated_message`
2. **TokenCounterWrapper** - for `_count_tokens`
3. **MessageSorter** - for sorting methods
4. **ValidationHelper** - for `validate_compacted_sequence`

### Phase 3: Consolidate Duplicate Code
- Extract common logic from `_sort_messages_by_importance` and `_sort_clusters_by_importance`

### Phase 4: Break Long Methods
- Extract helper methods from `_apply_intelligent_truncation`
- Extract helper methods from `compact_with_result`

## Test Strategy:
1. Run existing tests to ensure they pass
2. Create new tests for extracted classes
3. Test backward compatibility
4. Test new config-based constructor