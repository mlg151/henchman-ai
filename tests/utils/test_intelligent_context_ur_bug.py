"""Test for ur/ru prefix bug in intelligent_context.py."""

import pytest
from henchman.utils.intelligent_context import ContentExtractor


def test_ur_prefix_invalid_python3():
    """Test that ur'hello' (invalid Python 3) is handled correctly.
    
    In Python 3, 'ur' is NOT a valid string prefix (SyntaxError).
    The parser should handle this edge case.
    """
    # Test 1: ur prefix (invalid in Python 3)
    content1 = '''```python
# This is invalid Python 3 syntax but might appear in code
x = ur'hello'
```'''
    
    result1 = ContentExtractor.extract_code_blocks(content1)
    assert len(result1) == 1, f"Expected 1 code block, got {len(result1)}"
    code1 = result1[0]
    # The code block should be extracted, even with invalid syntax
    print(f"Code block 1: {code1}")
    
    # Test 2: ru prefix (also invalid in Python 3)
    content2 = '''```python
x = ru'hello'
```'''
    
    result2 = ContentExtractor.extract_code_blocks(content2)
    assert len(result2) == 1, f"Expected 1 code block, got {len(result2)}"
    code2 = result2[0]
    print(f"Code block 2: {code2}")
    
    # Test 3: Valid prefix followed by invalid (r is valid, ur is not)
    content3 = '''```python
x = r'valid'
y = ur'invalid'
```'''
    
    result3 = ContentExtractor.extract_code_blocks(content3)
    assert len(result3) == 1, f"Expected 1 code block, got {len(result3)}"
    code3 = result3[0]
    print(f"Code block 3: {code3}")
    
    # Test 4: What about in a comment?
    content4 = '''```python
# This is a comment about ur'strings'
x = r'valid'
```'''
    
    result4 = ContentExtractor.extract_code_blocks(content4)
    assert len(result4) == 1, f"Expected 1 code block, got {len(result4)}"
    code4 = result4[0]
    print(f"Code block 4: {code4}")


def test_string_prefix_extraction_bug():
    """Test the actual bug in prefix extraction logic.
    
    The bug is in how prefixes are extracted when there are non-prefix
    characters mixed in.
    """
    # What if we have something like: x = ar'hello'
    # 'ar' is not a valid prefix (contains 'a' which is not r/u/b/f)
    # But the current logic walks backward from quote looking for r/u/b/f
    # It would find 'r' but not 'a' (since 'a' is not in the set)
    # So j would stop at position of 'a'
    # prefix_start = j + 1 = position of 'r'
    # prefix = 'r' (not 'ar')
    # _is_valid_string_prefix('r') returns True
    # So it would think 'r' is a string prefix, not 'ar'!
    # But 'ar'hello' is variable 'ar' followed by string 'hello' (invalid Python)
    content = '''```python
x = ar'hello'
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    print(f"Code block: {code}")
    # The question is: does the parser correctly handle this?
    # 'ar' is not a valid string prefix, so it should NOT treat ' as string delimiter
    # based on prefix detection. But the current logic would extract 'r' as prefix
    # and think it's valid!


if __name__ == "__main__":
    pytest.main([__file__, "-v"])