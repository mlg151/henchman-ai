#!/usr/bin/env python3
"""Critical test for line continuation bug."""

from henchman.utils.intelligent_context import ContentExtractor

# CRITICAL TEST: What if there's a backtick on the continued line?
# The parser might think it's a code block marker!
content = '''Some text
```python
s = "hello\\
```world"
print(s)
```
More text'''

print("Critical test: String with line continuation followed by backticks")
print(f"Content:\n{content}\n")

result = ContentExtractor.extract_code_blocks(content)
print(f"Result: {len(result)} blocks")

if len(result) == 0:
    print("✗ NO CODE BLOCKS EXTRACTED! Parser incorrectly interpreted ``` as ending code block!")
elif len(result) == 1:
    print("✓ 1 code block extracted")
    print(f"Block: {repr(result[0])}")
else:
    print(f"? {len(result)} code blocks extracted")
    for i, block in enumerate(result):
        print(f"Block {i}: {repr(block[:100])}...")

# The correct behavior: 
# - Opening ``` at line 2 starts code block
# - The ``` on line 4 is INSIDE the string (due to line continuation)
# - Closing ``` at line 6 ends code block
# - Should extract 1 code block: lines 2-6

# Buggy behavior:
# - Parser sees newline at end of line 3, ends string (incorrectly, missing line continuation)
# - Parser sees ``` on line 4, thinks it's ending code block
# - Extracts code block as lines 2-4
# - Then sees more text, maybe extracts another block or none