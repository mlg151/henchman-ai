"""Test to demonstrate the tuple bug in _extract_by_patterns with multiple capture groups."""

import re
from henchman.utils.intelligent_context import ContentExtractor


def test_multiple_capture_groups_bug():
    """Test that patterns with multiple capture groups cause AttributeError."""
    
    # Create a test pattern with multiple capture groups
    # Example: pattern that captures both error type and message separately
    test_patterns = [
        r"(Error): (.*?)(?:\n|$)",  # Two capture groups: type and message
    ]
    
    content = "Error: something went wrong\nError: another error"
    
    # Simulate what happens in _extract_by_patterns
    sections = []
    for pattern in test_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        print(f"Pattern: {pattern}")
        print(f"Matches: {matches}")
        print(f"Type of first match: {type(matches[0]) if matches else 'No matches'}")
        
        for match in matches:
            print(f"  Processing match: {match}")
            print(f"  Is tuple: {isinstance(match, tuple)}")
            if isinstance(match, tuple):
                print(f"  Tuple length: {len(match)}")
                print(f"  Tuple elements: {match}")
                # This will fail: match.strip() on a tuple
                try:
                    if match and match.strip():
                        sections.append(match.strip())
                except AttributeError as e:
                    print(f"  ERROR: {e}")
                    print("  This is the bug! Can't call .strip() on a tuple")
            else:
                # String case
                if match and match.strip():
                    sections.append(match.strip())
    
    print(f"\nFinal sections: {sections}")
    
    # Now let's see what happens if we modify the actual patterns
    print("\n\nTesting with actual error patterns modified to have multiple groups:")
    
    # Modify the error pattern to have multiple capture groups
    modified_patterns = [
        r"(Traceback) (\(most recent call last\):.*?(?:\n\n|$))",  # Two groups
        r"(?<!\w)(Error):(.*?(?:\n|$))",  # Two groups: "Error:" and message
    ]
    
    test_content = """Traceback (most recent call last):
  File "test.py", line 1
    raise Error
Error: test message"""
    
    for pattern in modified_patterns:
        matches = re.findall(pattern, test_content, re.IGNORECASE | re.DOTALL)
        print(f"\nPattern: {pattern}")
        print(f"Matches: {matches}")
        if matches:
            print(f"First match: {matches[0]}")
            print(f"Type: {type(matches[0])}")


def test_real_world_scenario():
    """Test a real-world scenario where this could break."""
    print("\n\nReal-world scenario test:")
    
    # Suppose someone adds a pattern like this to extract tool name and arguments separately
    tool_patterns = [
        r"(Tool call): (\w+)\((.*?)\)",  # Three capture groups
    ]
    
    content = "Tool call: read_file('test.txt')\nTool call: write_file('out.txt', 'data')"
    
    # This is what would happen in _extract_by_patterns
    sections = []
    for pattern in tool_patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            print(f"Match: {match}, Type: {type(match)}")
            # This will crash with AttributeError
            try:
                if match and match.strip():
                    sections.append(match.strip())
            except AttributeError as e:
                print(f"CRASH: {e}")
                return False
    
    return True


if __name__ == "__main__":
    test_multiple_capture_groups_bug()
    test_real_world_scenario()