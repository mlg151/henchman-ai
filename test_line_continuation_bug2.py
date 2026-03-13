#!/usr/bin/env python3
"""Test to demonstrate the line continuation bug with backticks."""

from henchman.utils.intelligent_context import ContentExtractor

# Test: String with line continuation containing backticks
content = '''```python
code = "hello\\
`world`"
print(code)
```'''
print("Test: String with line continuation containing backticks")
result = ContentExtractor.extract_code_blocks(content)
print(f"  Result: {len(result)} blocks")
if result:
    print(f"  Block: {repr(result[0])}")
    
# The string should be "hello`world`" (with backticks inside)
# If parser incorrectly ends string at newline, it might see `world` as a code block!

# Test 2: Triple-quoted string with newline (should NOT end string)
content2 = '''```python
msg = """hello
world"""
print(msg)
```'''
print("\nTest 2: Triple-quoted string with newline")
result2 = ContentExtractor.extract_code_blocks(content2)
print(f"  Result: {len(result2)} blocks")
if result2:
    print(f"  Block: {repr(result2[0])}")