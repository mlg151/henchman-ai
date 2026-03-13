"""Test for ar"`hello`" bug in intelligent_context.py."""

from henchman.utils.intelligent_context import ContentExtractor


def test_extract_code_blocks_ar_string_with_backtick():
    """Test that ar"`hello`" is correctly parsed.
    
    If ar" is incorrectly treated as apostrophe (not string delimiter),
    then the ` inside "`hello`" would be counted as a backtick,
    which could break code block parsing.
    """
    # Test: ar"`hello`" - variable ar followed by string containing backticks
    content = '''```python
result = ar"`hello`"
print(result)
```'''
    blocks = ContentExtractor.extract_code_blocks(content)
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}. Content: {repr(content)}"
    block = blocks[0]
    # The code should contain ar"`hello`"
    assert 'ar"`hello`"' in block, f"ar\"`hello`\" not preserved correctly: {block}"
    print("Test passed!")


def test_extract_code_blocks_complex_expression():
    """Test more complex expression with identifier before string."""
    # This is actually invalid Python (TypeError) but should still parse
    content = '''```python
x = 5
result = x"value is {x}"
print(result)
```'''
    blocks = ContentExtractor.extract_code_blocks(content)
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    block = blocks[0]
    # Should contain x"value is {x}"
    assert 'x"value is {x}"' in block, f"x\"value is {{x}}\" not preserved: {block}"
    print("Test passed!")


if __name__ == "__main__":
    test_extract_code_blocks_ar_string_with_backtick()
    test_extract_code_blocks_complex_expression()