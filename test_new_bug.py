#!/usr/bin/env python3
"""Test for a potential bug in intelligent_context.py."""

# Let me test the actual ContentExtractor.extract_code_blocks method
import sys
sys.path.insert(0, '/home/matthew/mlg-cli/src')

from henchman.utils.intelligent_context import ContentExtractor

# Test case: code block with r'\n"' inside
content = '''```python
print(r'\\n"')
```'''

print(f"Testing content:\n{content}")
result = ContentExtractor.extract_code_blocks(content)
print(f"\nExtracted {len(result)} code blocks:")
for i, block in enumerate(result):
    print(f"\nBlock {i}: {repr(block)}")
    
# The issue might be: when parsing r'\n"', the backslash escapes n, not quote
# But the parser might think the backslash escapes the quote
# This could cause incorrect parsing of the code block