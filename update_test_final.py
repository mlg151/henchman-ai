#!/usr/bin/env python3
with open('tests/agents/test_working_memory.py', 'r') as f:
    lines = f.readlines()

# Find and update the test
for i, line in enumerate(lines):
    if 'def test_parse_line_range_multiple_ranges(self):' in line:
        # Find the end of this test (next line starting with 'def test_' or end of class)
        start = i
        end = None
        for j in range(i+1, len(lines)):
            if lines[j].strip().startswith('def test_') or lines[j].strip().startswith('class '):
                end = j
                break
        if end is None:
            end = len(lines)
        
        # Replace the test
        new_test = '''    def test_parse_line_range_multiple_ranges(self):
        """Test parsing multiple ranges (comma-separated).
        
        BUG: LineRange.from_str doesn't support multiple ranges.
        We've added _parse_line_ranges method to handle multiple ranges.
        """
        # Test that LineRange.from_str still doesn't support multiple ranges
        result = LineRange.from_str("10-20,30-40")
        assert result is None  # LineRange.from_str doesn't support multiple ranges
        
        # Test that _parse_line_ranges handles multiple ranges
        ranges = WorkingMemory._parse_line_ranges("10-20,30-40")
        assert len(ranges) == 2
        assert ranges[0].start == 10
        assert ranges[0].end == 20
        assert ranges[1].start == 30
        assert ranges[1].end == 40

'''
        # Replace lines[start:end] with new_test
        lines[start:end] = [new_test]
        break

with open('tests/agents/test_working_memory.py', 'w') as f:
    f.writelines(lines)

print("Test updated")