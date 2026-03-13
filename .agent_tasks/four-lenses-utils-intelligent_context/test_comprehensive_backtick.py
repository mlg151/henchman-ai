"""Comprehensive test for backtick handling."""

from henchman.utils.intelligent_context import ContentExtractor

def test_backtick_edge_cases():
    """Test edge cases for backtick counting."""
    # Test 1: Single backtick (should not be extracted as code block)
    content = "`print('hello')`"
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Single backtick: {result}")
    assert len(result) == 0, "Single backtick should not be extracted as code block"
    
    # Test 2: Two backticks (should not be extracted as code block)
    content = "``print('hello')``"
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Two backticks: {result}")
    assert len(result) == 0, "Two backticks should not be extracted as code block"
    
    # Test 3: Three backticks (standard code block)
    content = "```print('hello')```"
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Three backticks: {result}")
    assert len(result) == 1, "Three backticks should be extracted as code block"
    
    # Test 4: Four backticks
    content = "````print('hello')````"
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Four backticks: {result}")
    assert len(result) == 1, "Four backticks should be extracted as code block"
    
    # Test 5: Mismatched backticks (3 opening, 4 closing)
    content = "```print('hello')````"
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Mismatched (3 opening, 4 closing): {result}")
    assert len(result) == 0, "Mismatched backticks should not be extracted"
    
    # Test 6: Backticks in string inside code block
    content = '''```python
print("`hello`")
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Backticks in string: {result}")
    assert len(result) == 1, "Should extract code block with backticks in string"
    assert 'print("`hello`")' in result[0]
    
    # Test 7: Nested backticks (backticks inside backticks)
    content = '''````
```
code
```
````'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Nested backticks: {result}")
    # This is tricky - the outer block has 4 backticks, inner has 3
    # Should extract the entire block including inner backticks
    assert len(result) == 1, "Should extract nested code block"
    
    print("\nAll tests passed!")

if __name__ == "__main__":
    test_backtick_edge_cases()