"""Test string prefix detection bug in extract_code_blocks."""

from henchman.utils.intelligent_context import ContentExtractor


def test_string_prefix_identifier_bug():
    """Test that string prefix detection incorrectly treats variable names as prefixes."""
    
    # Test case 1: br = "string" - br is a variable name, not a string prefix
    content1 = '''```python
br = "Hello\\nWorld"  # br is a variable, not bytes raw string
print(br)
```'''
    
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    print(f"Test 1 - br = \"string\":")
    print(f"  Number of blocks: {len(blocks1)}")
    if blocks1:
        print(f"  Block content: {blocks1[0][:100]}...")
        # Check if backslashes are preserved (they shouldn't be for regular string)
        if '\\\\' in blocks1[0]:
            print("  BUG: Backslashes preserved - treating br as raw string prefix!")
        else:
            print("  OK: Backslashes not preserved - br treated as variable")
    
    # Test case 2: arr = "string" - arr is a variable
    content2 = '''```python
arr = "Hello\\nWorld"  # arr is a variable (array), not a raw string
print(arr)
```'''
    
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    print(f"\nTest 2 - arr = \"string\":")
    print(f"  Number of blocks: {len(blocks2)}")
    if blocks2:
        print(f"  Block content: {blocks2[0][:100]}...")
        if '\\\\' in blocks2[0]:
            print("  BUG: Backslashes preserved - treating r in arr as raw string prefix!")
        else:
            print("  OK: Backslashes not preserved - arr treated as variable")
    
    # Test case 3: mybr = "string" - mybr is a variable
    content3 = '''```python
mybr = "Hello\\nWorld"  # mybr is a variable
print(mybr)
```'''
    
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    print(f"\nTest 3 - mybr = \"string\":")
    print(f"  Number of blocks: {len(blocks3)}")
    if blocks3:
        print(f"  Block content: {blocks3[0][:100]}...")
        if '\\\\' in blocks3[0]:
            print("  BUG: Backslashes preserved - treating br in mybr as raw string prefix!")
        else:
            print("  OK: Backslashes not preserved - mybr treated as variable")
    
    # Test case 4: Actual raw string r"string"
    content4 = '''```python
r = "regular string"  # r is a variable
s = r"raw string"  # r is a string prefix
print(r, s)
```'''
    
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    print(f"\nTest 4 - Mixed r variable and r prefix:")
    print(f"  Number of blocks: {len(blocks4)}")
    if blocks4:
        print(f"  Block content: {blocks4[0][:150]}...")
        # This is tricky - need to parse the Python to know which r is prefix
    
    # Test case 5: Edge case - at start of line
    content5 = '''```python
br = "not raw"
x = br"actually raw"
```'''
    
    blocks5 = ContentExtractor.extract_code_blocks(content5)
    print(f"\nTest 5 - br variable vs br prefix:")
    print(f"  Number of blocks: {len(blocks5)}")
    if blocks5:
        print(f"  Block content: {blocks5[0][:150]}...")


if __name__ == "__main__":
    test_string_prefix_identifier_bug()