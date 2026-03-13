#!/usr/bin/env python3
"""Test for escape at end of string."""

from henchman.utils.intelligent_context import ContentExtractor

# Test: String ending with escaped quote
content = '''```python
s = "test\\""  # String ends with escaped quote
print(s)
```'''
print("Test: String ending with escaped quote")
result = ContentExtractor.extract_code_blocks(content)
print(f"  Result: {len(result)} blocks")
if result:
    print(f"  Block: {repr(result[0])}")

# Actually, "test\"" is invalid Python! Unterminated string.
# The quote is escaped, so string doesn't end.
# Should be "test\\"" (backslash-backslash-quote) or "test\"" (escaped quote) inside longer string.

# Test: Raw string with backslash at end
content2 = '''```python
s = r"test\\"  # Raw string with backslash at end
print(s)
```'''
print("\nTest: Raw string with backslash at end")
result2 = ContentExtractor.extract_code_blocks(content2)
print(f"  Result: {len(result2)} blocks")
if result2:
    print(f"  Block: {repr(result2[0])}")