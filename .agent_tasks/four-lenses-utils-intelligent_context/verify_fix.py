#!/usr/bin/env python3
"""Verify the fix for mismatched fence bug."""

from henchman.utils.intelligent_context import ContentExtractor

def main():
    print("=== Verifying fix for mismatched fence bug ===\n")
    
    # Test case 1: 5 backticks closing a 3-backtick block (should NOT extract)
    print("Test 1: Mismatched fence (5 backticks closing 3-backtick block)")
    content1 = """Some text
```python
def hello():
    return "world"
`````
More text with stray backticks"""
    
    result1 = ContentExtractor.extract_code_blocks(content1)
    print(f"  Result: {len(result1)} code blocks extracted")
    if len(result1) == 0:
        print("  ✓ PASS: No code blocks extracted (correct - mismatched fence)")
    else:
        print(f"  ✗ FAIL: {len(result1)} code blocks extracted (incorrect)")
        for i, block in enumerate(result1):
            print(f"    Block {i}: {block[:50]}...")
    print()
    
    # Test case 2: Properly closed code block (should extract)
    print("Test 2: Properly closed fence (3 backticks closing 3-backtick block)")
    content2 = """Some text
```python
def hello():
    return "world"
```
More text"""
    
    result2 = ContentExtractor.extract_code_blocks(content2)
    print(f"  Result: {len(result2)} code blocks extracted")
    if len(result2) == 1 and "def hello():" in result2[0]:
        print("  ✓ PASS: Code block correctly extracted")
    else:
        print(f"  ✗ FAIL: Expected 1 code block, got {len(result2)}")
    print()
    
    # Test case 3: 2 backticks closing a 3-backtick block (should NOT extract)
    print("Test 3: Too few backticks (2 backticks closing 3-backtick block)")
    content3 = """Some text
```python
def hello():
    return "world"
``
More text"""
    
    result3 = ContentExtractor.extract_code_blocks(content3)
    print(f"  Result: {len(result3)} code blocks extracted")
    if len(result3) == 0:
        print("  ✓ PASS: No code blocks extracted (correct - too few backticks)")
    else:
        print(f"  ✗ FAIL: {len(result3)} code blocks extracted (incorrect)")
    print()
    
    # Test case 4: Edge case - exactly matching fence
    print("Test 4: Exactly matching fence (4 backticks closing 4-backtick block)")
    content4 = """Some text
````python
def hello():
    return "world"
````
More text"""
    
    result4 = ContentExtractor.extract_code_blocks(content4)
    print(f"  Result: {len(result4)} code blocks extracted")
    if len(result4) == 1 and "def hello():" in result4[0]:
        print("  ✓ PASS: Code block correctly extracted with 4-backtick fence")
    else:
        print(f"  ✗ FAIL: Expected 1 code block, got {len(result4)}")
    print()
    
    print("=== Summary ===")
    all_passed = (
        len(result1) == 0 and
        len(result2) == 1 and
        len(result3) == 0 and
        len(result4) == 1
    )
    
    if all_passed:
        print("✓ All tests passed! The bug is fixed.")
    else:
        print("✗ Some tests failed. The bug may not be fully fixed.")

if __name__ == "__main__":
    main()