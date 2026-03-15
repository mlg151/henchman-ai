#!/usr/bin/env python3
import sys

with open('src/henchman/agents/working_memory.py', 'r') as f:
    lines = f.readlines()

# Find and update the LineRange.from_str usage
for i, line in enumerate(lines):
    if 'rng = LineRange.from_str(match.lines_read)' in line:
        # Update this line and the next few lines
        lines[i] = '            ranges = self._parse_line_ranges(match.lines_read)\n'
        if i+1 < len(lines) and 'if rng:' in lines[i+1]:
            lines[i+1] = '            valid_ranges.extend(ranges)\n'
        break

with open('src/henchman/agents/working_memory.py', 'w') as f:
    f.writelines(lines)

print("Updated LineRange.from_str usage to _parse_line_ranges")