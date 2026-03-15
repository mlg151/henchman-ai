#!/usr/bin/env python3
with open('tests/agents/test_working_memory.py', 'r') as f:
    lines = f.readlines()

# Update the test to assert result is not None (should fail with current code)
for i, line in enumerate(lines):
    if 'def test_parse_line_range_multiple_ranges(self):' in line:
        # Find the assert line
        for j in range(i, min(i+20, len(lines))):
            if 'assert result is None' in lines[j]:
                lines[j] = '        assert result is not None  # This will FAIL with current code - BUG!\n'
                break
        break

with open('tests/agents/test_working_memory.py', 'w') as f:
    f.writelines(lines)

print("Test updated to assert result is not None")