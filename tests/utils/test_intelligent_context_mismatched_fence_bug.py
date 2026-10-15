"""Test for mismatched fence bug in intelligent_context.py."""

from henchman.utils.intelligent_context_extractor import ContentExtractor


def test_extract_code_blocks_mismatched_fence_bug():
    """Test that exposes bug where more backticks than opening count incorrectly closes fence.

    Bug: When a code block opens with ``` (3 backticks) and the closing fence has ````` (5 backticks),
    the parser incorrectly accepts it as a valid closing fence, leaving 2 stray backticks.

    With the fix: The parser should reject the mismatched fence and not extract the code block
    since there's no proper closing fence.
    """
    # Test case 1: 5 backticks closing a 3-backtick block (no proper closing)
    content = """Some text
```python
def hello():
    return "world"
`````
More text with stray backticks"""

    result = ContentExtractor.extract_code_blocks(content)

    # With the bug (before fix): Would incorrectly extract code block
    # With the fix: Should return empty list since no proper closing fence
    assert len(result) == 0, f"Expected 0 code blocks (no proper closing fence), got {len(result)}: {result}"

    # Test case 2: Properly closed code block should still work
    content2 = """Some text
```python
def hello():
    return "world"
```
More text"""

    result2 = ContentExtractor.extract_code_blocks(content2)
    assert len(result2) == 1, f"Expected 1 code block (properly closed), got {len(result2)}: {result2}"
    assert "def hello():" in result2[0]


def test_mismatched_fence_direct():
    """Direct test of the _check_fence bug."""
    from henchman.utils.intelligent_context_parser import FenceParams, _ParserState

    parser = _ParserState()
    parser.in_string = False
    parser.in_comment = False

    # Test: 5 backticks should NOT close a 3-backtick block
    text = "`````"
    parser.backtick_count = 5  # We've seen 5 backticks

    # This is the bug: it returns a FenceResult when it should return None
    params = FenceParams(content=text, opening_count=3)
    result = parser._check_fence(4, params)  # i=4 (last backtick), opening_count=3

    # With the bug: result is not None (incorrect)
    # After fix: result should be None
    assert result is None, f"Expected None for mismatched fence (5 backticks closing 3), got {result}"


def test_exact_match_fence():
    """Test that exact match works correctly."""
    from henchman.utils.intelligent_context_parser import FenceParams, _ParserState

    parser = _ParserState()
    parser.in_string = False
    parser.in_comment = False

    # Test: 3 backticks SHOULD close a 3-backtick block
    text = "```"
    parser.backtick_count = 3

    params = FenceParams(content=text, opening_count=3)
    result = parser._check_fence(2, params)  # i=2 (last backtick), opening_count=3

    # This should work
    assert result is not None, "Expected FenceResult for exact match (3 backticks), got None"
    assert result.found, "Expected found=True for exact match"


def test_too_few_backticks():
    """Test that too few backticks doesn't close."""
    from henchman.utils.intelligent_context_parser import FenceParams, _ParserState

    parser = _ParserState()
    parser.in_string = False
    parser.in_comment = False

    # Test: 2 backticks should NOT close a 3-backtick block
    text = "``"
    parser.backtick_count = 2

    params = FenceParams(content=text, opening_count=3)
    result = parser._check_fence(1, params)  # i=1 (last backtick), opening_count=3

    # This should already work (current code has this check)
    assert result is None, f"Expected None for too few backticks (2 closing 3), got {result}"
