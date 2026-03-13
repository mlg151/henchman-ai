"""Test to find a bug in _process_char method."""

from henchman.utils.intelligent_context import _ParserState


def test_comment_inside_string():
    """Test that # inside a string doesn't start a comment."""
    parser = _ParserState()
    
    # Test: "#" inside a string
    text = '"hello # world"'
    
    # Process the opening quote
    i = 0  # position of '"'
    result = parser._process_char(text, i, was_escaped=False)
    assert parser.in_string, "Should be in string after opening quote"
    
    # Process the '#' inside the string (position 7)
    i = 7
    result = parser._process_char(text, i, was_escaped=False)
    
    # Should NOT be in comment mode because we're inside a string
    assert not parser.in_comment, "# inside string should not start comment"
    print("✓ # inside string correctly doesn't start comment")


def test_escaped_quote_in_comment():
    """Test escaped quote in comment doesn't affect string parsing."""
    parser = _ParserState()
    
    # Test: comment containing escaped quote
    text = '# This is a comment with \" quote'
    
    # Process the '#'
    i = 0
    result = parser._process_char(text, i, was_escaped=False)
    assert parser.in_comment, "Should be in comment after #"
    
    # Process the '\' (position 28)
    i = 28
    # Actually, when in comment, _process_char returns early!
    # So backslash shouldn't be processed
    result = parser._process_char(text, i, was_escaped=False)
    print(f"Processing backslash in comment: in_comment={parser.in_comment}")


def test_backtick_in_comment():
    """Test backtick in comment doesn't affect backtick count."""
    parser = _ParserState()
    
    # Test: comment containing backtick
    text = '# This is a comment with ` backtick'
    
    # Process the '#'
    i = 0
    result = parser._process_char(text, i, was_escaped=False)
    assert parser.in_comment, "Should be in comment after #"
    
    # Process the '`' (position 27)
    i = 27
    result = parser._process_char(text, i, was_escaped=False)
    
    # When in comment, _process_char returns early and sets backtick_count = 0
    # So backtick_count should be 0
    assert parser.backtick_count == 0, "Backtick in comment should not increment backtick_count"
    print("✓ Backtick in comment correctly doesn't affect backtick_count")


def test_string_with_escaped_backslash_before_quote():
    """Test string with escaped backslash before quote."""
    parser = _ParserState()
    
    # Test: "\\"" - string ending with backslash-quote
    text = '"\\\\""'
    
    # This is actually: quote, backslash, backslash, quote, quote
    # The string should end at the third quote (escaped by backslash)
    # Actually, in Python: "\\"" is invalid! It's "\\" followed by ""
    # "\\" is a string containing backslash
    # Then "" is empty string
    # So actually "\\"" is valid: string containing backslash, followed by empty string
    
    print(f"Testing: {text!r}")
    for idx, char in enumerate(text):
        print(f"  Position {idx}: {char!r}")
    
    # Actually, let me test what the parser does
    i = 0  # opening quote
    result = parser._process_char(text, i, was_escaped=False)
    print(f"  After opening quote: in_string={parser.in_string}")
    
    i = 1  # first backslash
    result = parser._process_char(text, i, was_escaped=False)
    print(f"  After first backslash: escape_next={parser.escape_next}")
    
    i = 2  # second backslash
    # was_escaped should be True from previous backslash
    was_escaped = parser.escape_next
    parser.escape_next = False
    result = parser._process_char(text, i, was_escaped=was_escaped)
    print(f"  After second backslash: was_escaped={was_escaped}, in_string={parser.in_string}")


if __name__ == "__main__":
    print("Testing for bugs in _process_char...")
    print("=" * 60)
    test_comment_inside_string()
    print()
    test_escaped_quote_in_comment()
    print()
    test_backtick_in_comment()
    print()
    test_string_with_escaped_backslash_before_quote()