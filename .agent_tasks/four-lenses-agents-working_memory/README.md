# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T18:00:00Z
## Bug Summary
The `get_file_insights` method returns insights only from the MOST RECENT entry for a file, losing valuable historical context. A working memory system should accumulate ALL insights from ALL reads of a file to provide complete context.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Working memory should retain ALL insights gained from ALL reads of a file | Only the most recent insights are retained |
| Historical context should be preserved for comprehensive understanding | Historical insights are discarded when new reads occur |
| The method should provide a complete picture of what was learned about a file | Provides only a partial, most-recent snapshot |

## Root Cause
The `get_file_insights` method uses `next((e.key_insights for e in reversed(self.recent_files) if e.path == path), [])` which returns only the first (most recent) matching entry's insights. It should accumulate insights from ALL matching entries.

## Test Case
```python
memory = WorkingMemory(current_task="Test")
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First", "1-50", ["Old insight 1", "Old insight 2"]))
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second", "60-100", ["New insight 1", "New insight 2", "New insight 3"]))

insights = memory.get_file_insights("/test/file.py")
# Current: ["New insight 1", "New insight 2", "New insight 3"] (most recent only)
# Fixed: ["Old insight 1", "Old insight 2", "New insight 1", "New insight 2", "New insight 3"] (all insights)
```

## Fix Plan
1. Modify `get_file_insights` to iterate through ALL entries and accumulate insights
2. Return insights in chronological order (oldest first) for logical progression
3. Update the test to expect accumulated insights instead of just most recent

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `get_file_insights` method
2. `tests/agents/test_working_memory.py` - Updated `test_memory_get_file_insights_multiple_entries` test

## Status: FIXED