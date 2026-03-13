"""Test to demonstrate the identifier checking bug in extract_code_blocks."""

import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import ContentExtractor

def test_extract_code_blocks_raw_string_after_identifier():
    """Test bug: raw string prefix after identifier ending with same letter."""
    # The bug: when we have an identifier ending with 'r' followed by raw string
    # The prefix detection logic might incorrectly think 'r' is part of identifier
    content = '''```python
# Identifier ending with 'r' followed by raw string
arr = r"test"
brr = r"test2"
cr = r"test3"
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    
    # Should extract one code block
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    code = blocks[0]
    # All raw strings should be preserved
    assert 'arr = r"test"' in code, f"Missing arr: {code}"
    assert 'brr = r"test2"' in code, f"Missing brr: {code}"
    assert 'cr = r"test3"' in code, f"Missing cr: {code}"

def test_extract_code_blocks_string_prefix_with_whitespace():
    """Test that string prefixes work with various whitespace."""
    content = '''```python
# Different whitespace before prefix
s1=r"test1"  # no space
s2 =r"test2" # space before =
s3= r"test3" # space after =
s4 = r"test4" # spaces both sides
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    code = blocks[0]
    # All should work
    assert 's1=r"test1"' in code, f"Missing s1: {code}"
    assert 's2 =r"test2"' in code, f"Missing s2: {code}"
    assert 's3= r"test3"' in code, f"Missing s3: {code}"
    assert 's4 = r"test4"' in code, f"Missing s4: {code}"

def test_extract_code_blocks_not_raw_string():
    """Test that 'r' in middle of string is not treated as prefix."""
    content = '''```python
# 'r' not at start of string literal
s1 = "test"
s2 = "raw"
s3 = "r"  # just the letter r
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    code = blocks[0]
    # Should not have raw string markers
    assert 's1 = "test"' in code, f"Missing s1: {code}"
    assert 's2 = "raw"' in code, f"Missing s2: {code}"
    assert 's3 = "r"' in code, f"Missing s3: {code}"

if __name__ == "__main__":
    print("Testing identifier checking bug in extract_code_blocks...")
    
    tests = [
        test_extract_code_blocks_raw_string_after_identifier,
        test_extract_code_blocks_string_prefix_with_whitespace,
        test_extract_code_blocks_not_raw_string,
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