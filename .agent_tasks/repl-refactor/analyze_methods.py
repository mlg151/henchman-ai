#!/usr/bin/env python3
"""Analyze REPL method line ranges."""

import re

def analyze_repl_methods():
    with open('src/henchman/cli/repl.py', 'r') as f:
        lines = f.readlines()
    
    methods = []
    current_method = None
    start_line = 0
    method_indent = 0
    
    for i, line in enumerate(lines, 1):
        # Check for method definition (look for 'def ' at the beginning of a line after whitespace)
        if line.lstrip().startswith('def '):
            if current_method:
                methods.append((current_method, start_line, i-1))
            
            # Extract method name
            method_match = re.match(r'\s*def\s+(\w+)', line)
            if method_match:
                current_method = method_match.group(1)
                start_line = i
                method_indent = len(line) - len(line.lstrip())
    
    # Add last method
    if current_method:
        methods.append((current_method, start_line, len(lines)))
    
    print("REPL Method Analysis:")
    print("=" * 50)
    for method, start, end in methods:
        line_count = end - start + 1
        print(f"{method:30} lines {start:3}-{end:3} ({line_count:3} lines)")
    
    total_lines = len(lines)
    print(f"\nTotal lines in REPL: {total_lines}")
    
    # Calculate how many lines we need to remove
    target_lines = 400
    lines_to_remove = total_lines - target_lines
    print(f"Need to remove at least {lines_to_remove} lines to reach {target_lines} lines")
    
    # Show largest methods first
    print("\nLargest methods (target for reduction):")
    print("-" * 50)
    sorted_methods = sorted(methods, key=lambda x: x[2]-x[1], reverse=True)
    for method, start, end in sorted_methods[:5]:
        line_count = end - start + 1
        print(f"{method:30} {line_count:3} lines")

if __name__ == '__main__':
    analyze_repl_methods()