#!/usr/bin/env python3
"""Test to demonstrate the escape handling bug."""

from henchman.utils.intelligent_context import ContentExtractor

# Test 1: Regular string with escaped quote
content1 = '''```python
print("He said \\"hello\\"")
```'''
print("Test 1: Regular string with escaped quote")
result1 = ContentExtractor.extract_code_blocks(content1)
print(f"  Result: {len(result1)} blocks")
if result1:
    print(f"  Block: {repr(result1[0])}")

# Test 2: Raw string with backslash (should not escape)
content2 = '''```python
print(r"Backslash: \\")
```'''
print("\nTest 2: Raw string with backslash")
result2 = ContentExtractor.extract_code_blocks(content2)
print(f"  Result: {len(result2)} blocks")
if result2:
    print(f"  Block: {repr(result2[0])}")

# Test 3: Raw string with escaped quote (should escape quote but not backslash)
content3 = '''```python
print(r"Quote: \\"")
```'''
print("\nTest 3: Raw string with escaped quote")
result3 = ContentExtractor.extract_code_blocks(content3)
print(f"  Result: {len(result3)} blocks")
if result3:
    print(f"  Block: {repr(result3[0])}")

# Test 4: Multiple backslashes in raw string
content4 = '''```python
print(r"\\\\")
```'''
print("\nTest 4: Multiple backslashes in raw string")
result4 = ContentExtractor.extract_code_blocks(content4)
print(f"  Result: {len(result4)} blocks")
if result4:
    print(f"  Block: {repr(result4[0])}")