"""Test for double quote apostrophe bug in intelligent_context.py."""

from henchman.utils.intelligent_context import ContentExtractor


def test_extract_code_blocks_double_quote_not_apostrophe():
    """Test that double quotes are never treated as apostrophes in words.
    
    In Python code, double quotes (") are always string delimiters,
    never apostrophes in words. The heuristic for detecting apostrophes
    in words should only apply to single quotes (').
    """
    # Test: Double quote with alnum on both sides should still be string delimiter
    # This is invalid Python but tests the parser logic
    content = '''```python
x"test"
```'''
    blocks = ContentExtractor.extract_code_blocks(content)
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}. Content: {repr(content)}"
    block = blocks[0]
    # Should contain x"test"
    assert 'x"test"' in block, f"x\"test\" not preserved: {block}"
    print("Test 1 passed!")
    
    # Test: Valid Python with double-quoted string
    content2 = '''```python
s = "hello"
print(s)
```'''
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block, got {len(blocks2)}"
    block2 = blocks2[0]
    assert '"hello"' in block2, f"\"hello\" not preserved: {block2}"
    print("Test 2 passed!")
    
    # Test: Edge case - double quote at end of identifier
    content3 = '''```python
identifier"string"
```'''
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    if blocks3:
        block3 = blocks3[0]
        assert 'identifier"string"' in block3, f"identifier\"string\" not preserved: {block3}"
    print("Test 3 passed!")
    
    # Test: Single quote might be apostrophe in comment
    content4 = '''```python
# This isn't a string
x = 1
```'''
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    assert len(blocks4) == 1, f"Expected 1 code block, got {len(blocks4)}"
    block4 = blocks4[0]
    assert "isn't" in block4, f"isn't not preserved in comment: {block4}"
    print("Test 4 passed!")


if __name__ == "__main__":
    test_extract_code_blocks_double_quote_not_apostrophe()