"""Test for triple quote bug in intelligent_context.py.

Test triple quote string parsing bug.
"""

import pytest
from henchman.utils.intelligent_context_parser import _ParserState


def test_triple_quote_string_parsing():
    """Test triple quote string parsing."""
    parser = _ParserState()
    
    # Test triple double quotes: """hello"""
    text = '"""hello"""'
    
    # Start parsing at position 0
    i = 0
    
    # Process first quote - should start triple quote string
    # handle_string_start should detect triple quote and return i + 2 = 2
    new_i = parser.handle_string_start(text, i)
    assert new_i == 2  # Skip to third quote
    assert parser.in_string == True
    assert parser.triple_quote == True
    assert parser.string_char == '"'
    
    # Now i = 2 (third quote of opening triple)
    # This is still part of the opening delimiter, not content
    # The next character (position 3) is 'h' (start of content)
    
    # Simulate parsing through content
    # Position 2 is the third quote of opening delimiter
    # We're inside a string, so this quote shouldn't end the string
    # unless it's followed by two more quotes
    
    # Fast forward to position 8 (first quote of closing triple)
    i = 8  # Position of 'h' is 3, 'e'4, 'l'5, 'l'6, 'o'7, '"'8
    
    # At position 8, we're in a triple-quoted string
    # This quote might be the start of closing triple quote
    # handle_string_end should check if i+1 and i+2 are also quotes
    # They are: positions 9 and 10 are '"'
    # So it should end the string and return i + 2 = 10
    new_i = parser.handle_string_end(text, i)
    
    # Fixed: Should return i + 3 = 11 (position after third quote)
    # This skips all three quotes of the closing delimiter
    
    assert new_i == 11  # Fixed behavior - position after third quote
    assert parser.in_string == False  # String ended
    
    # Position 11 is after the closing triple quote
    # This is correct - we've consumed all three quotes


def test_triple_quote_in_code_block():
    """Test triple quotes inside code blocks."""
    from henchman.utils.intelligent_context_extractor import ContentExtractor
    
    # Code block with triple-quoted string
    content = '''```python
print("""Hello world""")
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    
    assert len(blocks) == 1
    # Should extract the full code
    assert 'print("""Hello world""")' in blocks[0]


def test_mixed_quotes_in_code():
    """Test mixed single and triple quotes in code."""
    from henchman.utils.intelligent_context_extractor import ContentExtractor
    
    content = '''```python
s1 = 'single'
s2 = """triple"""
s3 = "double"
```'''
    
    blocks = ContentExtractor.extract_code_blocks(content)
    
    assert len(blocks) == 1
    # All strings should be preserved
    assert "s1 = 'single'" in blocks[0]
    assert 's2 = """triple"""' in blocks[0]
    assert 's3 = "double"' in blocks[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])