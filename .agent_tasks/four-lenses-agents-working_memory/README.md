# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T05:00:00Z
## Bug Summary
The `should_read_file` method only checks the MOST RECENT file entry when determining if lines have been read, causing unnecessary re-reading when a file has been read multiple times with the most recent read being a subset of earlier reads.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `should_read_file` should check ALL previous reads for a file to determine if lines have been read | Only checks the most recent entry, causing unnecessary re-reads |
| Union of all read ranges should be considered when checking containment | Only the most recent range is checked, wasting API calls and context window |
| Working memory should prevent ALL unnecessary file reads, not just those against the most recent read | Performance degradation and increased costs due to redundant reads |

## Root Cause
In the `should_read_file` method, line 241:
```python
match = next((e for e in reversed(self.recent_files) if e.path == path), None)
```

This finds the FIRST (most recent) matching file entry using `reversed(self.recent_files)`. The method then only checks against this single entry, not considering that the file might have been read multiple times with different line ranges.

**Example bug scenario**:
1. File read fully: lines 1-100
2. File read partially later: lines 10-50 (for specific analysis)
3. Ask: should I read lines 60-80?
4. Current: Checks against most recent (10-50) → 60-80 not contained → returns True (read it)
5. **BUG**: Lines 60-80 WERE read in step 1! Should return False.

## Fix Plan
1. Modify `should_read_file` to check ALL entries for the file, not just the most recent
2. For each entry, check if requested range is contained
3. If ANY entry contains the requested range, return False (don't read)
4. Otherwise, return True (need to read)
5. Update tests to verify the fix

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `should_read_file` method to check ALL entries for a file instead of just the most recent one
2. `tests/agents/test_working_memory.py` - Updated test expectations to match corrected behavior

## Changes Made
1. **Bug Fix**: `should_read_file` now iterates through ALL matching file entries (not just most recent) to check if requested line range is contained in ANY previous read
2. **Logic Update**: Added tracking of `found_valid_range` to distinguish between "no valid ranges found" (invalid format) and "valid ranges found but none cover requested range"
3. **Test Correction**: Updated test expectation in `test_memory_should_read_file_multiple_entries_same_file` to expect correct behavior (lines 60-80 should return False when file was previously read fully as 1-100)

## Verification
- All 48 tests in `tests/agents/test_working_memory.py` pass
- Custom test `test_proper_failing_test.py` confirms bug is fixed
- The fix prevents unnecessary re-reading when most recent read is a subset of earlier reads