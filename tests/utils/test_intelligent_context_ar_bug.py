"""Test for ar"test" bug in intelligent_context.py."""

from henchman.utils.intelligent_context_extractor import ContentExtractor


def test_extract_code_blocks_ar_string_bug():
    """Test that ar"test" is correctly parsed as identifier followed by string.
    
    This test exposes a bug where ar"test" is incorrectly treated as having
    an apostrophe in a word (like "isn't") instead of as a string delimiter.
    """
    # Test 1: ar"test" - should be parsed as identifier 'ar' followed by string '"test"'
    # (or as function call ar("test") if ar is a function)
    content1 = '''```python
result = ar"test"
print(result)
```'''
    blocks1 = ContentExtractor.extract_code_blocks(content1)
    assert len(blocks1) == 1, f"Expected 1 code block, got {len(blocks1)}. Content: {repr(content1)}"
    block1 = blocks1[0]
    # The code should contain ar"test"
    assert 'ar"test"' in block1, f"ar\"test\" not preserved correctly: {block1}"
    
    # Test 2: More complex example with variable before string
    content2 = '''```python
x = 5
y = x"hello"  # This is invalid Python (TypeError) but should still parse
```'''
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    # Should extract the code block
    if blocks2:
        block2 = blocks2[0]
        # Should contain x"hello"
        assert 'x"hello"' in block2, f"x\"hello\" not preserved: {block2}"
    
    # Test 3: Valid Python with method call
    content3 = '''```python
s = "hello"
print(s.upper())
```'''
    blocks3 = ContentExtractor.extract_code_blocks(content3)
    assert len(blocks3) == 1, f"Expected 1 code block, got {len(blocks3)}"
    block3 = blocks3[0]
    # Should contain s.upper()
    assert 's.upper()' in block3, f"s.upper() not preserved: {block3}"
    
    # Test 4: Edge case - single character identifier before string
    content4 = '''```python
a"test"
```'''
    blocks4 = ContentExtractor.extract_code_blocks(content4)
    # Should extract
    if blocks4:
        block4 = blocks4[0]
        assert 'a"test"' in block4, f"a\"test\" not preserved: {block4}"
    
    print("All tests passed!")


if __name__ == "__main__":
    test_extract_code_blocks_ar_string_bug()