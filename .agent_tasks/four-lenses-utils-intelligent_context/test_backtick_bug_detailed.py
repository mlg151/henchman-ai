"""Detailed test for backtick counting bug in intelligent_context.py"""

from henchman.utils.intelligent_context import ContentExtractor

def test_backtick_counting_detailed():
    """Test that code extraction handles backtick counting correctly with exact positions."""
    # Test with 3 backticks
    content = '''```python
print("hello")
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"3 backticks result: {result[0] if result else 'None'}")
    assert len(result) == 1
    # Check that the result doesn't contain the closing backticks
    assert result[0] == '```python\nprint("hello")\n```'
    
    # Test with 4 backticks - more likely to expose the bug
    content = '''````python
print("hello")
````'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"4 backticks result: {result[0] if result else 'None'}")
    assert len(result) == 1
    # The extracted block should be ```python\nprint("hello")\n``` not `````python\nprint("hello")\n````
    assert result[0] == '```python\nprint("hello")\n```'
    
    # Test with code that has backticks in it
    content = '''````python
print("```")
````'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Code with backticks result: {result[0] if result else 'None'}")
    assert len(result) == 1
    assert 'print("```")' in result[0]
    
    # Test edge case: empty code block
    content = '''````
````'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Empty code block result: {result[0] if result else 'None'}")
    assert len(result) == 1
    assert result[0] == '```\n```'  # Should be 3 backticks, not 4
    
    print("\nAll tests passed!")

if __name__ == "__main__":
    test_backtick_counting_detailed()