"""Test for backtick counting bug in intelligent_context.py"""

from henchman.utils.intelligent_context import ContentExtractor

def test_backtick_counting():
    """Test that code extraction handles backtick counting correctly."""
    # Test with 3 backticks (standard)
    content = '''```python
print("hello")
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"3 backticks result: {result}")
    assert len(result) == 1
    assert 'print("hello")' in result[0]
    
    # Test with 4 backticks
    content = '''````python
print("hello")
````'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"4 backticks result: {result}")
    assert len(result) == 1
    assert 'print("hello")' in result[0]
    
    # Test with mismatched backticks (should not extract)
    content = '''```python
print("hello")
````'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Mismatched backticks result: {result}")
    # This might fail if the bug exists
    
    # Test with backticks in string
    content = '''```python
print("`hello`")
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Backticks in string result: {result}")
    assert len(result) == 1
    assert 'print("`hello`")' in result[0]

if __name__ == "__main__":
    test_backtick_counting()
    print("All tests passed!")