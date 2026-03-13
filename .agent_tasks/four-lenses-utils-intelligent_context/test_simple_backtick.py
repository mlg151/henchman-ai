"""Simple test for backtick at line start bug."""

import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import ContentExtractor

# Simple test case
content = '''```python
`test`
```'''

print(f"Content: {repr(content)}")
print(f"Content length: {len(content)}")

# Let me trace through what should happen
# Position 0-2: ``` (opening)
# Position 3-9: python\n (language + newline)
# Position 10: ` (backtick at start of line after \n)
# This should NOT be mistaken for closing backticks!

blocks = ContentExtractor.extract_code_blocks(content)
print(f"Blocks extracted: {len(blocks)}")
if blocks:
    print(f"Block: {repr(blocks[0])}")
else:
    print("No block extracted!")

# Let me also test with the exact string from the failing test
content2 = '''```python
# Line starting with backtick
`this looks like closing but isn't`
print("done")
```'''

print(f"\n\nContent2: {repr(content2)}")
blocks2 = ContentExtractor.extract_code_blocks(content2)
print(f"Blocks2 extracted: {len(blocks2)}")
if blocks2:
    print(f"Block2: {repr(blocks2[0])}")

# Actually, looking at the output, I notice something.
# The backtick line is: `this looks like closing but isn't`
# That has a backtick at start AND end!
# So we have: ` ... ` on a single line.
# This looks like inline code in markdown!
# Maybe the function is interpreting it as ending the code block?

# Let me test without the closing backtick
content3 = '''```python
# Line starting with backtick
`this looks like closing but isn't
print("done")
```'''

print(f"\n\nContent3 (no closing backtick): {repr(content3)}")
blocks3 = ContentExtractor.extract_code_blocks(content3)
print(f"Blocks3 extracted: {len(blocks3)}")
if blocks3:
    print(f"Block3: {repr(blocks3[0])}")