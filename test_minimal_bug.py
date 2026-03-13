#!/usr/bin/env python3
"""Minimal test to find a bug."""

from henchman.utils.intelligent_context import ContentExtractor

# Simplest possible test: empty code block
content = '``````'
print(f"Test 1: 6 backticks: {repr(content)}")
result = ContentExtractor.extract_code_blocks(content)
print(f"  Result: {len(result)} blocks")
if result:
    print(f"  Block: {repr(result[0])}")

# Test from existing test file: test_extract_code_blocks_empty_code_blocks
# says "6 consecutive backticks is not a valid code block"
# But what does the code actually do?

# Let me trace through the logic:
# _count_backticks counts 6 backticks
# find_closing_fence looks for closing fence with count=6
# It parses the content (which is just 6 backticks)
# When does it find a closing fence?

# Actually, 6 backticks: ``````
# Opening fence: first 3 backticks
# Closing fence: next 3 backticks
# Code content: empty
# Should extract 1 code block with empty content?

print("\nChecking implementation...")
import inspect
print("Looking at _count_backticks method:")
from henchman.utils.intelligent_context import ContentExtractor as CE
source = inspect.getsource(CE._count_backticks)
print(source[:200])