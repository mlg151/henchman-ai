"""Check for magic numbers in intelligent_context.py."""

import re
import ast

with open('src/henchman/utils/intelligent_context.py', 'r') as f:
    content = f.read()

# Find numeric literals
lines = content.split('\n')
for i, line in enumerate(lines, 1):
    # Look for numeric literals (integers or floats)
    # This is a simple regex, not perfect but good enough
    matches = re.findall(r'\b\d+(?:\.\d+)?\b', line)
    for match in matches:
        # Skip 0, 1, -1 which are often not magic numbers
        if match in ['0', '1', '-1', '0.0', '1.0', '-1.0']:
            continue
        # Skip line numbers in comments
        if 'line' in line.lower() and match.isdigit():
            continue
        print(f"Line {i}: Potential magic number: {match} in: {line.strip()[:80]}")