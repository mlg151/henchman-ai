"""Test to demonstrate the capture group bug in _extract_by_patterns."""

import re
from henchman.utils.intelligent_context import ContentExtractor


def test_extract_error_sections_capture_group_bug():
    """Test that error sections are extracted incorrectly due to capture groups."""
    
    # Create a content with an error traceback
    content = """Some normal text.
Traceback (most recent call last):
  File "test.py", line 1, in <module>
    raise ValueError("test error")
ValueError: test error

Some more text.
Error: something went wrong
Exception: another issue
warning: be careful
failure: operation failed"""

    # Extract error sections
    result = ContentExtractor.extract_error_sections(content)
    
    print("Extracted error sections:")
    for i, section in enumerate(result):
        print(f"{i}: {repr(section)}")
    
    # The bug: patterns have capture groups, so findall returns only captured content
    # Let's demonstrate what re.findall actually returns
    print("\n\nDebug: What re.findall returns for each pattern:")
    
    patterns = ContentExtractor._PATTERN_REGISTRY["error"]
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
        print(f"\nPattern: {pattern}")
        print(f"Matches: {matches}")
        if matches:
            print(f"First match type: {type(matches[0])}")
            if isinstance(matches[0], tuple):
                print(f"First match tuple length: {len(matches[0])}")
    
    # Expected: Full traceback including "Traceback (most recent call last):"
    # Actual: Might be missing parts or incorrect
    
    # Let's also test with a simpler case
    print("\n\nSimple test case:")
    simple_content = "Error: test error\nNormal text"
    simple_result = ContentExtractor.extract_error_sections(simple_content)
    print(f"Simple content: {repr(simple_content)}")
    print(f"Extracted: {repr(simple_result)}")
    
    # The pattern is: r"(?<!\w)Error:.*?(?:\n|$))"
    # This has a capture group, so findall returns only what's captured
    # Which is "Error:.*?(?:\n|$)" - but wait, the entire pattern is captured!
    # Actually, the entire pattern is in a capture group, so it should return the full match
    # Let me check more carefully...
    
    # Actually, I need to check if the non-capturing group affects things
    test_pattern = r"(?<!\w)Error:.*?(?:\n|$)"
    test_matches = re.findall(test_pattern, simple_content, re.IGNORECASE)
    print(f"\nTest pattern: {test_pattern}")
    print(f"Test matches: {test_matches}")
    
    # Wait, let me trace through the actual logic
    print("\n\nTracing actual function logic:")
    
    # Simulate _extract_by_patterns
    sections = []
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
        print(f"\nPattern: {pattern[:50]}...")
        print(f"Number of matches: {len(matches)}")
        for match in matches:
            print(f"  Match type: {type(match)}, value: {repr(match)[:100]}...")
            if match and match.strip():
                sections.append(match.strip())
    
    print(f"\nFinal sections extracted: {sections}")


if __name__ == "__main__":
    test_extract_error_sections_capture_group_bug()