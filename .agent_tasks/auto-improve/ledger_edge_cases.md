# Edge Cases for agents/ledger.py Refactoring

## Current Smells to Address:
1. **Duplicate __init__ methods** - False positive? Simple constructors with different signatures
2. **Duplicate counting methods** - `_get_delegation_counts_static` vs utility functions
3. **Duplicate `add_checklist_item` and `add_delegation`** - Already addressed with `_add_item_factory`
4. **Duplicate `complete_delegation`** - Similar structure to other methods
5. **Duplicate `render` method** - Similar to other rendering methods

## Edge Cases to Test:

### 1. Empty State Handling
- Ledger with no goal (should not happen, goal is required)
- Ledger with empty checklist and delegations
- Rendering when max_entries = 0 or negative

### 2. Boundary Conditions
- Checklist with exactly 1 item
- Delegations exactly at max_entries threshold
- Summary truncation at exactly SUMMARY_MAX_LENGTH (500)
- Negative indices for check_item()

### 3. Type Safety
- Passing wrong type to `_format_progress_line`
- Passing empty list to counting utilities
- Passing None where not expected

### 4. Rendering Edge Cases
- Very long goal strings
- Delegations with multiline summaries
- Unicode characters in task descriptions
- Mix of completed, pending, failed delegations

### 5. Factory Method Edge Cases
- `_add_item_factory` with different factory functions
- Error handling in factory methods

## Test Plan:
1. Write tests for each edge case
2. Refactor to eliminate duplicate code
3. Ensure all existing tests pass
4. Add new tests for uncovered edge cases