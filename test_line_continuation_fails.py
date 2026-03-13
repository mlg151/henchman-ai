#!/usr/bin/env python3
"""Test that should fail due to line continuation bug."""

from henchman.utils.intelligent_context import ContentExtractor

# The bug: parser ends string at newline even with line continuation
# This could cause backticks on next line to be misinterpreted

# Test with actual problematic case
content = '''Some text
```python
print("Line 1\\
`Line 2`")
```
More text'''

print("Test: String with line continuation and backticks")
print(f"Content:\n{content}\n")

result = ContentExtractor.extract_code_blocks(content)
print(f"Result: {len(result)} blocks")

# The code block should be extracted
# But if parser incorrectly ends string at newline:
# - Sees ` on next line (not in string)
# - Might think it's a code block marker
# - Could extract wrong code block or fail

if len(result) != 1:
    print(f"✗ Expected 1 block, got {len(result)}")
    for i, block in enumerate(result):
        print(f"Block {i}: {repr(block[:100])}...")
else:
    print("✓ 1 block extracted")
    # Check if content is correct
    block = result[0]
    if '`Line 2`' in block:
        print("✓ Backticks preserved in string")
    else:
        print("✗ Backticks not preserved!")
    
# Actually run the Python code to see what it should be
print("\nActual Python code would be:")
code = '''print("Line 1\\
`Line 2`")'''
print(f"Code: {repr(code)}")
print(f"Output: ", end='')
exec(code)