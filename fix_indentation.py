#!/usr/bin/env python3
with open('src/henchman/agents/working_memory.py', 'r') as f:
    lines = f.readlines()

# Find and fix the issue
for i, line in enumerate(lines):
    if 'valid_ranges.extend(ranges)' in line and i+1 < len(lines) and 'valid_ranges.append(rng)' in lines[i+1]:
        # Remove the next line
        lines[i+1] = ''
        break

with open('src/henchman/agents/working_memory.py', 'w') as f:
    f.writelines(lines)

print("Fixed indentation error")