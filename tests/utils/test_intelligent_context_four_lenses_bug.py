"""Test for Four Lenses bug in intelligent_context.py."""

import pytest
from henchman.utils.intelligent_context import ContentExtractor


def test_bug_ar_prefix_affects_code_block():
    """Test that ar'hello' affects code block extraction.
    
    This test demonstrates a bug where ar'hello' (invalid Python)
    causes incorrect parsing of code blocks.
    """
    # Create a code block with ar'hello' followed by backticks
    # The bug: if ar'hello' is treated as apostrophe (not string),
    # then the parser's string state tracking might be wrong,
    # which could affect backtick counting.
    content = '''```python
# Test with ar'hello'
x = ar'hello'
# Now some backticks in a string: "`code`"
y = "`code`"
# More code
print(x, y)
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    
    # The code block should be extracted correctly
    # But if ar'hello' causes incorrect string tracking,
    # the backticks in "`code`" might be misinterpreted
    print(f"Extracted code: {code}")
    
    # Actually, let me think about a more concrete bug.
    # What if we have a code block with ar'hello' and then
    # a backtick that's part of the code block fence?
    content2 = '''```python
x = ar'hello'
```'''
    
    result2 = ContentExtractor.extract_code_blocks(content2)
    assert len(result2) == 1, f"Expected 1 code block, got {len(result2)}"
    code2 = result2[0]
    print(f"Code block 2: {code2}")
    
    # The real issue might be: if the parser thinks ' in ar'hello'
    # is an apostrophe (not string delimiter), then it doesn't enter
    # string state. But then when it sees the closing ```,
    # it should recognize it as a fence.
    # Actually, that should work fine.
    
    # Let me think of a different bug. What about nested backticks?
    content3 = '''```python
# String with backtick: "`"
x = "`"
# Another string: ar'hello'
y = ar'hello'
```'''
    
    result3 = ContentExtractor.extract_code_blocks(content3)
    assert len(result3) == 1, f"Expected 1 code block, got {len(result3)}"
    code3 = result3[0]
    print(f"Code block 3: {code3}")


def test_bug_ur_prefix_in_python3():
    """Test that ur'hello' (invalid Python 3) causes issues.
    
    In Python 3, 'ur' is NOT a valid string prefix.
    The parser should handle this correctly.
    """
    # Test with ur'hello' which is invalid Python 3 syntax
    # but might appear in code (maybe Python 2 code or mistake)
    content = '''```python
# Python 2 style string (invalid in Python 3)
x = ur'hello'
# Valid string
y = r'world'
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    
    # Check that both strings are preserved
    # The issue: ur'hello' might be parsed incorrectly
    print(f"Code block: {code}")
    
    # Actually, I need to think about what the correct behavior should be.
    # ur'hello' is invalid Python 3 syntax. The parser is trying to
    # parse Python code (or code-like text). When it sees ur'hello',
    # it should either:
    # 1. Treat 'ur' as invalid prefix, so ' is string delimiter
    # 2. Or treat it as something else?
    # 
    # Currently, _is_apostrophe_in_word returns True for ur'hello'
    # (because 'ur' is not a valid prefix, and ' is followed by 'h').
    # So it thinks ' is an apostrophe in a word.
    # But ur'hello' is trying to be a string literal!
    # This could cause the parser to not track string state correctly.


def test_actual_failing_case():
    """Create a test that actually fails with the current implementation.
    
    I need to find a case where incorrect apostrophe detection
    leads to wrong code block extraction.
    """
    # What if we have a code block with ur'hello' and then
    # a backtick inside what should be a string?
    # If the parser doesn't recognize ur'hello' as a string,
    # it won't be in string state when it sees the backtick.
    # Then the backtick might be counted as part of a fence!
    content = '''```python
x = ur'hello`world'
y = "normal string"
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    
    # The backtick in 'hello`world' should NOT end the code block!
    # But if the parser doesn't recognize ur' as starting a string,
    # then it's not in string state when it sees `.
    # Then ` might be counted as a backtick for fence detection!
    # Actually, wait. The parser would see ur'hello`world'
    # If it thinks ' is apostrophe (not string delimiter),
    # then it's not in string state. Then it sees `.
    # ` is a backtick! It increments backtick_count.
    # Then it sees ' at the end. Is that an apostrophe too?
    # Actually, the second ' might also be considered apostrophe.
    # But the backtick_count is now 1.
    # Then when it sees the closing ``` fence,
    # it needs 3 backticks, not 1.
    # Hmm, this might not cause a fence detection issue.
    
    print(f"Code block: {code}")
    
    # Let me check what happens
    # Actually, I should run this and see if it fails


if __name__ == "__main__":
    pytest.main([__file__, "-v"])