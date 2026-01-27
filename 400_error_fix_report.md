# 400 Error Fix Report: Context Length Exceeded

## Problem
The user encountered a 400 error from the LLM provider due to exceeding the context length limit (128k tokens). The request size was ~600k tokens.
This was caused by the `grep` tool returning a massive amount of output (approx 5.8 million characters) when searching a large directory/file.

## Root Cause
The `GrepTool` and `LsTool` did not have any limits on the size of the output they returned.
- `GrepTool`: Would read all matching lines from all matching files into memory and return them.
- `LsTool`: Would list all files in a directory.

## Solution
Implemented safety limits in `GrepTool` and `LsTool`.

### GrepTool Changes (`src/henchman/tools/builtins/grep.py`)
- Added `MAX_MATCHES = 1000`
- Added `MAX_OUTPUT_CHARS = 100_000` (approx 25k tokens)
- The tool now stops processing when either limit is reached and appends a truncation message:
  `... Output truncated (limit reached: X matches or Y chars) ...`

### LsTool Changes (`src/henchman/tools/builtins/ls.py`)
- Added `MAX_ITEMS = 1000`
- The tool now lists at most 1000 items and appends a truncation message if more exist.

### Additional Safety Improvements

#### ShellTool (`src/henchman/tools/builtins/shell.py`)
- Added `MAX_OUTPUT_CHARS = 100_000`
- Truncates output if it exceeds the limit.

#### GlobTool (`src/henchman/tools/builtins/glob_tool.py`)
- Added `MAX_MATCHES = 1000`
- Truncates the list of matching files if it exceeds the limit.

#### ContextCompactor (`src/henchman/utils/compaction.py`)
- Added a "Final Safety Net": `enforce_safety_limits` method.
- Before compacting, every individual message is checked using token counting (`tiktoken`).
- If any message's token count exceeds **75% of the configured max_tokens**, it is truncated.
- This ensures that no single message can crash the context window, while being less aggressive than fixed character limits.

## Verification
- Created a reproduction script `reproduce_context_overflow.py` that generated a large file.
- Before fix: Output was ~5.8MB, causing context overflow.
- After fix: Output was truncated to ~55KB, safely within context limits.
- Validated `ContextCompactor` safety limits with `tests/e2e/test_context_safety.py`.

These changes prevent the agent from accidentally crashing the conversation by reading or listing too much data.
