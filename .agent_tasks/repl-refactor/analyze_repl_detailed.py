#!/usr/bin/env python3
"""Detailed REPL method analysis."""

def analyze_repl_detailed():
    with open('src/henchman/cli/repl.py') as f:
        lines = f.readlines()

    methods = []
    current_method = None
    start_line = 0
    in_method = False
    method_indent = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Check for method definition
        if stripped.startswith('def '):
            if current_method:
                methods.append((current_method, start_line, i-1))

            # Extract method name
            parts = stripped.split('def ')[1].split('(')
            method_name = parts[0].strip()
            current_method = method_name
            start_line = i
            method_indent = len(line) - len(line.lstrip())
            in_method = True

        # Check for end of method (next method or end of class)
        elif in_method and stripped and not line.startswith(' ' * method_indent):
            # This line is not indented under the method, so method ended
            if current_method:
                methods.append((current_method, start_line, i-1))
                current_method = None
                in_method = False

    # Add last method if we're still in one
    if current_method:
        methods.append((current_method, start_line, len(lines)))

    print("Detailed REPL Method Analysis:")
    print("=" * 60)

    total_lines = 0
    for method, start, end in methods:
        line_count = end - start + 1
        total_lines += line_count
        print(f"{method:25} lines {start:3}-{end:3} ({line_count:3} lines)")

        # Show first few lines of the method
        print("  " + lines[start-1].rstrip())
        if start < len(lines):
            next_line = lines[start].rstrip()
            if next_line:
                print("  " + next_line[:80] + ("..." if len(next_line) > 80 else ""))
        print()

    print(f"\nTotal method lines: {total_lines}")
    print(f"Total file lines: {len(lines)}")

    # Calculate how many lines we need to remove
    target_lines = 400
    lines_to_remove = len(lines) - target_lines
    print(f"Need to remove at least {lines_to_remove} lines to reach {target_lines} lines")

    # Show largest methods first
    print("\nLargest methods (target for reduction):")
    print("-" * 60)
    sorted_methods = sorted(methods, key=lambda x: x[2]-x[1], reverse=True)
    for method, start, end in sorted_methods:
        line_count = end - start + 1
        if line_count > 10:  # Only show substantial methods
            print(f"{method:25} {line_count:3} lines")

if __name__ == '__main__':
    analyze_repl_detailed()
