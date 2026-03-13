"""Test traceback extraction bug in _extract_by_patterns."""

import re
from henchman.utils.intelligent_context import ContentExtractor


def test_traceback_pattern_bug():
    """Test that traceback pattern incorrectly includes text after traceback."""
    
    # Test case 1: Traceback followed by single newline and more text
    content1 = """Some text before.
Traceback (most recent call last):
  File "test.py", line 1
    raise ValueError("test")
ValueError: test
Some text after the traceback.
More text."""
    
    result1 = ContentExtractor.extract_error_sections(content1)
    print(f"Test 1 - Traceback with single newline after:")
    print(f"  Extracted: {result1}")
    if result1:
        extracted = result1[0]
        print(f"  Length: {len(extracted)}")
        print(f"  Includes 'Some text after'? {'Some text after' in extracted}")
        if 'Some text after' in extracted:
            print("  BUG: Includes text after traceback!")
        else:
            print("  OK: Doesn't include text after traceback")
    
    # Test case 2: Traceback at end of content (no trailing newline)
    content2 = """Traceback (most recent call last):
  File "test.py", line 1
    raise ValueError("test")
ValueError: test"""
    
    result2 = ContentExtractor.extract_error_sections(content2)
    print(f"\nTest 2 - Traceback at end (no newline):")
    print(f"  Extracted: {result2}")
    
    # Test case 3: Traceback with double newline after (correct case)
    content3 = """Traceback (most recent call last):
  File "test.py", line 1
    raise ValueError("test")
ValueError: test

Next paragraph."""
    
    result3 = ContentExtractor.extract_error_sections(content3)
    print(f"\nTest 3 - Traceback with double newline after:")
    print(f"  Extracted: {result3}")
    if result3:
        extracted = result3[0]
        print(f"  Includes 'Next paragraph'? {'Next paragraph' in extracted}")
    
    # Test case 4: Multiple tracebacks
    content4 = """First traceback:
Traceback (most recent call last):
  File "a.py", line 1
    raise Error
Error: first

Second traceback:
Traceback (most recent call last):
  File "b.py", line 2
    raise Error
Error: second
End."""
    
    result4 = ContentExtractor.extract_error_sections(content4)
    print(f"\nTest 4 - Multiple tracebacks:")
    print(f"  Number extracted: {len(result4)}")
    for i, r in enumerate(result4):
        print(f"  {i}: {r[:50]}...")
    
    # Let's also examine what the regex actually matches
    print("\n\nDebug - What the regex matches:")
    pattern = r"(Traceback \(most recent call last\):.*?(?:\n\n|$))"
    
    test_cases = [
        ("Single newline after", content1),
        ("No newline at end", content2),
        ("Double newline", content3),
    ]
    
    for name, content in test_cases:
        matches = re.findall(pattern, content, re.DOTALL)
        print(f"\n{name}:")
        print(f"  Number of matches: {len(matches)}")
        if matches:
            match = matches[0]
            print(f"  Match length: {len(match)}")
            print(f"  Match ends with: {repr(match[-20:])}")
            # Check if match ends with \n\n
            if match.endswith('\n\n'):
                print("  Ends with \\n\\n - correct")
            elif match.endswith('\n'):
                print("  Ends with \\n - might be correct or bug")
            else:
                print("  Ends with no newline - might be correct or bug")


if __name__ == "__main__":
    test_traceback_pattern_bug()