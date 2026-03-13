"""Test to demonstrate the real string prefix detection bug in extract_code_blocks."""

import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import ContentExtractor

def test_extract_code_blocks_string_prefix_index_error():
    """Test the actual bug: when i == 1 and we check content[i-2], we get content[-1]."""
    # Create a code block where the first character after opening backticks is a quote
    # with a prefix at position i=1 relative to some context
    content = '''```
r"test"
```'''
    
    # When parsing this, at some point i will be 1 when we encounter the quote after r
    # The bug is in the prefix detection logic
    blocks = ContentExtractor.extract_code_blocks(content)
    
    # Should extract one code block
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    assert 'r"test"' in blocks[0], f"Code block should contain raw string: {blocks[0]}"

def test_extract_code_blocks_complex_raw_string():
    """Test with complex raw string that should work."""
    content = '''```python
# Test raw string with escaped quote
s1 = r"\\""
# Test regular string with escaped backtick  
s2 = "`"
# Test raw string with backtick
s3 = r"`"
# Test string that looks like prefix but isn't
s4 = "r"
# Test actual raw string
s5 = r"raw"
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    code = blocks[0]
    # Check key strings are preserved
    assert 's1 = r"\\""' in code, f"Missing s1: {code}"
    assert 's2 = "`"' in code, f"Missing s2: {code}"
    assert 's3 = r"`"' in code, f"Missing s3: {code}"
    assert 's4 = "r"' in code, f"Missing s4: {code}"
    assert 's5 = r"raw"' in code, f"Missing s5: {code}"

def test_extract_code_blocks_prefix_detection_edge_case():
    """Test edge case where prefix might be misidentified."""
    content = '''```python
# 'r' as part of a variable name followed by string
arr = ["item"]
# Now a raw string  
s = r"test"
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    code = blocks[0]
    assert 's = r"test"' in code, f"Should contain raw string: {code}"

if __name__ == "__main__":
    print("Testing real string prefix bug in extract_code_blocks...")
    
    tests = [
        test_extract_code_blocks_string_prefix_index_error,
        test_extract_code_blocks_complex_raw_string,
        test_extract_code_blocks_prefix_detection_edge_case,
    ]
    
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__} passed")
        except AssertionError as e:
            print(f"✗ {test.__name__} failed (assertion): {e}")
        except Exception as e:
            print(f"✗ {test.__name__} failed (exception): {e}")
            import traceback
            traceback.print_exc()