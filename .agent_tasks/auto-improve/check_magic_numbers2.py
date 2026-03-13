"""Check for magic numbers in code (not in constant definitions)."""

import re

with open('src/henchman/utils/intelligent_context.py', 'r') as f:
    content = f.read()

# Skip the constants class
lines = content.split('\n')
in_constants_class = False
for i, line in enumerate(lines, 1):
    # Check if we're entering or leaving the constants class
    if 'class IntelligentContextConstants:' in line:
        in_constants_class = True
        continue
    if in_constants_class and line.strip() and not line.startswith('    '):
        # Left the constants class
        in_constants_class = False
    
    if in_constants_class:
        continue  # Skip constants
    
    # Look for numeric literals (integers or floats)
    matches = re.findall(r'\b\d+(?:\.\d+)?\b', line)
    for match in matches:
        # Skip 0, 1, -1 which are often not magic numbers
        if match in ['0', '1', '-1', '0.0', '1.0', '-1.0']:
            continue
        # Skip line numbers in comments
        if 'line' in line.lower() and match.isdigit():
            continue
        # Skip common small numbers that might be okay
        if match in ['2', '3', '5', '10', '100']:
            # Check if it's in a comment about tokens or lines
            if 'token' not in line.lower() and 'line' not in line.lower():
                print(f"Line {i}: Potential magic number: {match} in: {line.strip()[:80]}")