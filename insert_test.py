#!/usr/bin/env python3
import sys

with open('tests/agents/test_working_memory.py', 'r') as f:
    lines = f.readlines()

# Find where to insert the test
insert_at = None
for i, line in enumerate(lines):
    if 'def test_parse_line_range_single_number(self):' in line:
        # Find the end of this test (next line starting with 'def test_' or end of class)
        for j in range(i, len(lines)):
            if j > i and lines[j].strip().startswith('def test_'):
                insert_at = j
                break
        if insert_at is None:
            insert_at = len(lines)
        break

if insert_at is not None:
    # Insert the new test
    new_test = '''    def test_parse_line_range_multiple_ranges(self):
        """Test parsing multiple ranges (comma-separated).
        
        BUG: LineRange.from_str doesn't support multiple ranges.
        It should either parse the first range or support all ranges.
        Currently returns None for "10-20,30-40".
        """
        result = LineRange.from_str("10-20,30-40")
        # Currently returns None, but should return LineRange(10, 20) at minimum
        # or ideally we should have a different method that parses multiple ranges
        assert result is None  # This is the bug - should not be None

'''
    lines.insert(insert_at, new_test)
    
    with open('tests/agents/test_working_memory.py', 'w') as f:
        f.writelines(lines)
    print(f"Test inserted at line {insert_at}")
else:
    print("Could not find insertion point")
    sys.exit(1)