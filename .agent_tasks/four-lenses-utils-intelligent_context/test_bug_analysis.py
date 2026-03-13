"""Test to analyze the bug in _check_closing_fence method."""

import pytest
from henchman.utils.intelligent_context import _ParserState, FenceResult


def test_check_closing_fence_bug():
    """Test that exposes a bug in _check_closing_fence logic."""
    parser = _ParserState()
    
    # Test case 1: Simple case - should work
    parser.backtick_count = 3
    parser.in_string = False
    parser.in_comment = False
    text = "```"
    result = parser._check_closing_fence(text, 2, 3)  # i=2 (last backtick)
    assert result is not None
    assert result.found
    assert result.code_end == 0  # i - (backtick_count - 1) = 2 - (3-1) = 2 - 2 = 0
    
    # Test case 2: Backticks inside a string - should return None
    parser.backtick_count = 3
    parser.in_string = True
    result = parser._check_closing_fence(text, 2, 3)
    assert result is None
    
    # Test case 3: Backticks in comment - should return None
    parser.in_string = False
    parser.in_comment = True
    result = parser._check_closing_fence(text, 2, 3)
    assert result is None
    
    # Test case 4: Not enough backticks - should return None
    parser.in_comment = False
    parser.backtick_count = 2
    result = parser._check_closing_fence(text, 2, 3)
    assert result is None
    
    # Test case 5: Edge case - backtick followed by alnum
    parser.backtick_count = 3
    text2 = "```python"
    result = parser._check_closing_fence(text2, 2, 3)
    assert result is None  # Should return None because next char is 'p' (alnum)
    
    # Test case 6: Edge case - backtick followed by underscore
    text3 = "```_test"
    result = parser._check_closing_fence(text3, 2, 3)
    assert result is None  # Should return None because next char is '_'
    
    # Test case 7: Edge case - backtick followed by another backtick (more backticks)
    text4 = "````"
    result = parser._check_closing_fence(text4, 2, 3)
    assert result is None  # Should return None because next char is '`'
    
    # Test case 8: The bug - what if i+1 is out of bounds?
    text5 = "```"
    # Simulate being at the last character where i+1 would be out of bounds
    # The current code checks: if i + 1 < text_length
    # If i+1 == text_length, then we don't check next_char
    # This is correct, but let's test it
    result = parser._check_closing_fence(text5, 2, 3)
    assert result is not None  # Should return a result
    
    # Test case 9: Potential bug - what about backtick_count > opening_count?
    parser.backtick_count = 4  # More backticks than opening
    result = parser._check_closing_fence(text5, 2, 3)
    # This should return a result because backtick_count >= opening_count
    # But wait, if we have 4 backticks but opening_count is 3, is that valid?
    # Actually, if we have ````` (5 backticks) and opening was ``` (3),
    # then we need to find exactly 3 backticks to close, not 5.
    # So backtick_count should equal opening_count, not just be >=
    # THIS IS THE BUG!
    print(f"Test 9: backtick_count=4, opening_count=3, result={result}")
    # The current code checks: if self.backtick_count < opening_count: return None
    # So backtick_count=4, opening_count=3: 4 < 3 is False, so it continues
    # This means it would accept ````` as closing for ``` which is wrong!
    
    # Let me verify this is actually a bug by looking at the logic more carefully
    # Actually, wait. The backtick_count is incremented for each backtick we see.
    # If we see ````` (5 backticks), we would have backtick_count=5 at the last backtick.
    # But the check happens after each character is processed.
    # So when we see the 4th backtick, backtick_count=4, opening_count=3
    # The condition checks if 4 < 3 (false), so it continues
    # Then it checks if next_char is '`' (yes, because there's a 5th backtick)
    # So is_closing = False, and it returns None
    # Then we process the 5th backtick, backtick_count=5
    # 5 < 3 is false, continue
    # next_char doesn't exist (end of string), so is_closing = True
    # So it would return a FenceResult!
    # This means ````` would close a ``` block, which is wrong!
    
    # Actually, let me re-examine. The code has:
    # if i + 1 < text_length:
    #     next_char = text[i + 1]
    #     if next_char.isalnum() or next_char == "_":
    #         is_closing = False
    #     elif next_char == "`":
    #         # If next character is also a backtick, we're in a longer
    #         # backtick sequence. Continue parsing to consume all backticks.
    #         is_closing = False
    # 
    # So for `````, when we're at the 3rd backtick (i=2):
    # - backtick_count=3
    # - i+1=3 < text_length=5, next_char='`'
    # - is_closing=False, returns None
    # Then we continue to i=3 (4th backtick):
    # - backtick_count=4
    # - i+1=4 < 5, next_char='`'
    # - is_closing=False, returns None
    # Then we continue to i=4 (5th backtick):
    # - backtick_count=5
    # - i+1=5 is NOT < text_length=5
    # - So we skip the if block, is_closing=True (default)
    # - Returns FenceResult!
    # 
    # So yes, ````` would close a ``` block. That's a bug!