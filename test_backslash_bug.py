#!/usr/bin/env python3
"""Test for backslash escaping bug in intelligent_context.py."""

import sys
sys.path.insert(0, '/home/matthew/mlg-cli/src')

from henchman.utils.intelligent_context import ContentExtractor

# Test case: single-quoted string with backslash before double quote
# 'hello\"world' - backslash doesn't escape double quote
# The backslash is literal because it's not escaping the string delimiter
content1 = '''```python
print('hello\\"world')
```'''

print(f"Test 1: Single-quoted string with backslash-double-quote")
print(f"Content:\n{content1}")
result1 = ContentExtractor.extract_code_blocks(content1)
print(f"Extracted {len(result1)} code blocks")
if result1:
    print(f"Block: {repr(result1[0])}")

# Test case: double-quoted string with backslash before single quote  
# "hello\'world" - backslash doesn't escape single quote
content2 = '''```python
print("hello\\'world")
```'''

print(f"\n\nTest 2: Double-quoted string with backslash-single-quote")
print(f"Content:\n{content2}")
result2 = ContentExtractor.extract_code_blocks(content2)
print(f"Extracted {len(result2)} code blocks")
if result2:
    print(f"Block: {repr(result2[0])}")

# Test what Python actually does
print("\n\nPython behavior test:")
print("'hello\\\"world': ", end="")
try:
    exec('x = \'hello\\"world\'')
    print(f"VALID: {repr(x)}")
except SyntaxError as e:
    print(f"SyntaxError: {e}")

print('"hello\\\'world": ', end="")
try:
    exec('x = "hello\\\'world"')
    print(f"VALID: {repr(x)}")
except SyntaxError as e:
    print(f"SyntaxError: {e}")