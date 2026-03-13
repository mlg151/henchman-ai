#!/usr/bin/env python3
"""Test for newline escaped bug."""

from henchman.utils.intelligent_context import ContentExtractor

# Test: String with escaped newline \n (backslash-n)
content1 = '''```python
s = "hello\\nworld"
print(s)
```'''
print("Test 1: String with escaped newline \\n")
result1 = ContentExtractor.extract_code_blocks(content1)
print(f"  Result: {len(result1)} blocks")
if result1:
    print(f"  Block: {repr(result1[0])}")

# The string "hello\\nworld" has \n (newline character)
# Parser sees \, handles it, sets escape_next = True
# Next char is 'n', was_escaped = True
# String continues (good)

# Test: String with actual newline (not escaped)
content2 = '''```python
s = "hello
world"
print(s)
```'''
print("\nTest 2: String with actual newline (invalid Python)")
result2 = ContentExtractor.extract_code_blocks(content2)
print(f"  Result: {len(result2)} blocks")

# This is invalid Python (string spans line without triple quotes or line continuation)
# Parser should end string at newline

# Test: String with line continuation \\
content3 = '''```python
s = "hello\\
world"
print(s)
```'''
print("\nTest 3: String with line continuation \\\\")
result3 = ContentExtractor.extract_code_blocks(content3)
print(f"  Result: {len(result3)} blocks")
if result3:
    print(f"  Block: {repr(result3[0])}")

# String "hello\\\nworld" has backslash then newline (line continuation)
# Parser sees \, handles it, sets escape_next = True
# Next char is newline, was_escaped = True
# Current bug: ends string at newline even though was_escaped = True!
# Should NOT end string!

# Actually run the Python code
print("\nActual Python behavior for Test 3:")
code = '''s = "hello\\
world"
print(repr(s))'''
exec(code)
print("String continues across line (line continuation)")