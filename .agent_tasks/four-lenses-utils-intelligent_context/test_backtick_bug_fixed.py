"""Test for backtick counting bug in extract_code_blocks."""

import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import ContentExtractor

def test_extract_code_blocks_with_backtick_in_string():
    """Test code block with backtick in string literal."""
    content = '''```python
s = "`"  # backtick in string
print(s)
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    assert 's = "`"' in blocks[0], f"Should contain backtick in string: {blocks[0]}"

def test_extract_code_blocks_with_escaped_backtick():
    """Test code block with escaped backtick."""
    content = '''```python
s = "\\`"  # escaped backtick in string
print(s)
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    # Note: "\\`" in Python string is "\`"
    assert 's = "\\`"' in blocks[0] or 's = "\\\\`"' in blocks[0], f"Should contain escaped backtick: {blocks[0]}"

def test_extract_code_blocks_with_multiple_backticks():
    """Test code block with multiple backticks."""
    content = '''```python
# Backticks in comments ` ` `
s1 = "`"
s2 = '`'
s3 = """`"""
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    # Should extract the whole block

def test_extract_code_blocks_backtick_at_line_start():
    """Test tricky case: backtick at start of line inside code block."""
    content = '''```python
# Line starting with backtick
`this looks like closing but isn't`
print("done")
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    assert '`this looks like closing but isn\'t`' in blocks[0], f"Should contain backtick line: {blocks[0]}"

def test_extract_code_blocks_consecutive_backticks_in_code():
    """Test consecutive backticks in code (not closing)."""
    content = '''```python
# Consecutive backticks
print("``")
print("```")
print("````")
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    assert 'print("``")' in blocks[0], f"Should contain double backticks: {blocks[0]}"
    assert 'print("```")' in blocks[0], f"Should contain triple backticks: {blocks[0]}"

if __name__ == "__main__":
    print("Testing backtick handling in extract_code_blocks...")
    
    tests = [
        test_extract_code_blocks_with_backtick_in_string,
        test_extract_code_blocks_with_escaped_backtick,
        test_extract_code_blocks_with_multiple_backticks,
        test_extract_code_blocks_backtick_at_line_start,
        test_extract_code_blocks_consecutive_backticks_in_code,
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