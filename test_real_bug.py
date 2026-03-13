#!/usr/bin/env python3
"""Test for a real bug in intelligent_context.py."""

import sys
sys.path.insert(0, '/home/matthew/mlg-cli/src')

from henchman.utils.intelligent_context import ContentExtractor

# I need to think of an edge case that breaks the code...
# Let me test the raw string backslash counting logic

# The bug I suspect: in _handle_backslash method, it counts consecutive backslashes
# But what if there's a backslash that's not escaping the immediately following character?
# Example: in a regular (non-raw) string, backslash escapes next character
# But what about: "\\\"" - that's backslash, backslash, quote
# The first backslash escapes the second backslash
# The quote is not escaped
# But the code might think the quote is escaped?

# Actually, let me test a different edge case: string prefixes with numbers?
# Like "123r'hello'" - "123r" is not a valid prefix
# But the code might think it is?

test_cases = [
    # Test 1: Invalid prefix "123r"
    ("123r'hello'", "Should not extract as code block if malformed"),
    
    # Test 2: What about "R" uppercase at beginning of line?
    ("R'hello'", "Uppercase R should be recognized as raw string prefix"),
    
    # Test 3: What about backslash at end of line (line continuation)?
    ("x = 'hello \\\n world'", "Backslash at end of line continues string"),
]

for i, (content, description) in enumerate(test_cases):
    print(f"\nTest {i+1}: {description}")
    print(f"Content: {repr(content)}")
    
    # Wrap in code block
    code_block = f"```python\n{content}\n```"
    result = ContentExtractor.extract_code_blocks(code_block)
    print(f"Extracted {len(result)} code blocks")
    if result:
        print(f"First block: {repr(result[0][:100])}...")