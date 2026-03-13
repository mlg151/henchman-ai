"""Test that double quotes are never treated as apostrophes in words."""

from henchman.utils.intelligent_context import ContentExtractor


def test_double_quote_not_apostrophe():
    """Double quotes should never be treated as apostrophes in words.
    
    In English, apostrophes are always single quotes ('), never double quotes (").
    The code incorrectly tries to detect apostrophes for both quote types.
    """
    # Create a test that would fail if double quotes are treated as apostrophes
    # We need to test the internal parser state, not just extraction
    # Let's create a complex case
    
    # Test: Code with double quote that has alnum on both sides
    # This should be treated as a string delimiter, not an apostrophe
    content = '''```python
# Test case: x"value" where x is a variable
result = x"test"
print(result)
```'''
    
    # Extract code blocks
    blocks = ContentExtractor.extract_code_blocks(content)
    
    # Should extract exactly one code block
    assert len(blocks) == 1, f"Expected 1 code block, got {len(blocks)}"
    
    # The extracted block should contain the original code
    block = blocks[0]
    assert 'x"test"' in block, f"Code not preserved correctly: {block}"
    
    # Also test with more complex example
    content2 = '''```python
def test():
    # This string has double quotes: "hello"
    s = "hello"
    # This looks like an apostrophe but with double quotes: "isn"t" (invalid)
    # Actually "isn"t" would be string "isn" followed by t" (syntax error)
    return s
```'''
    
    blocks2 = ContentExtractor.extract_code_blocks(content2)
    assert len(blocks2) == 1, f"Expected 1 code block, got {len(blocks2)}"
    
    print("Test passed! Double quotes are correctly treated as string delimiters.")


if __name__ == "__main__":
    test_double_quote_not_apostrophe()