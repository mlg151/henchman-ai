# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T13:00:00Z
## Bug Summary
The `should_read_file` method has incorrect error message logic when invalid line ranges are provided. When `start > end` (e.g., start=10, end=5), the method returns `True` with message "Invalid line range: start (10) > end (5) - treating as new read". The phrase "treating as new read" is misleading because it suggests the file needs to be read due to the invalid range, not because of the invalidity itself.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Invalid input should be clearly reported as such | Misleading message suggests file needs reading due to range gap |
| Error message should explain the actual problem | Message conflates "invalid input" with "need to read file" |
| Caller should understand their input was rejected | Caller might think "Oh, I need to read lines 10-5" (nonsense) |

## Root Cause
The error message at line 388: `f"Invalid line range: start ({start}) > end ({end}) - treating as new read"` uses the phrase "treating as new read" which implies the method is making a decision about whether to read the file based on the range. Actually, the method is rejecting invalid input. The `True` return value means "should read" but in this case it's because the input is invalid, not because of any analysis of file reading history.

## Fix Plan
Change the error message to clearly indicate the input is invalid without suggesting a file reading decision was made. Example: `f"Invalid line range: start ({start}) > end ({end})"` or `f"Invalid line range: start ({start}) > end ({end}) - line numbers must be in ascending order"`.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Line 388: Changed error message from "treating as new read" to "line numbers must be in ascending order"
2. `tests/agents/test_working_memory_error_message.py` - Added new test file to verify the fix

## Verification
- All existing tests pass: `python -m pytest tests/agents/test_working_memory.py -x`
- New test passes: `python -m pytest tests/agents/test_working_memory_error_message.py::test_should_read_file_invalid_range_error_message -xvs`
- The error message is now clear and not misleading: "Invalid line range: start (10) > end (5) - line numbers must be in ascending order"