import re

with open('tests/agents/test_working_memory.py', 'r') as f:
    content = f.read()

# Find the test_parse_line_range_single_number test and add after it
pattern = r'(def test_parse_line_range_single_number\(self\):\s*"""Test parsing single number as line range\."""\s*result = LineRange\.from_str\("10"\)\s*assert result is None\s*)'
match = re.search(pattern, content, re.DOTALL)
if match:
    new_test = '''    def test_parse_line_range_single_number(self):
        """Test parsing single number as line range."""
        result = LineRange.from_str("10")
        assert result is None

    def test_parse_line_range_multiple_ranges(self):
        """Test parsing multiple ranges (comma-separated).
        
        BUG: LineRange.from_str doesn't support multiple ranges.
        It should either parse the first range or support all ranges.
        Currently returns None for "10-20,30-40".
        """
        result = LineRange.from_str("10-20,30-40")
        # Currently returns None, but should return LineRange(10, 20) at minimum
        # or ideally we should have a different method that parses multiple ranges
        assert result is None  # This is the bug - should not be None

    def test_line_range_overlaps_true(self):'''
    
    # Replace from the match start to the next def
    rest = content[match.end():]
    next_def = re.search(r'^\s*def test_', rest, re.MULTILINE)
    if next_def:
        # Replace the section
        new_content = content[:match.start()] + new_test + rest[next_def.start():]
        with open('tests/agents/test_working_memory.py', 'w') as f:
            f.write(new_content)
        print("Test added successfully")
    else:
        print("Could not find next test")
else:
    print("Could not find test_parse_line_range_single_number")