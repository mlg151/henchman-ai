#!/usr/bin/env python3
"""Fix whitespace issues in working_memory.py."""

import re

def fix_whitespace(file_path: str) -> None:
    """Fix trailing whitespace in docstrings."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix: lines with only whitespace in docstrings (W293)
    # Pattern: match lines with only whitespace between triple quotes
    lines = content.split('\n')
    in_docstring = False
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # Check if we're entering/exiting a docstring
        stripped = line.strip()
        
        # Handle multi-line docstrings
        if stripped.startswith('"""') or stripped.startswith("'''"):
            # Check if it's opening or closing
            if stripped.count('"""') == 1 and stripped.count("'''") == 0:
                # Single triple quote - could be opening or closing
                if not in_docstring:
                    in_docstring = True
                else:
                    in_docstring = False
            elif stripped.count("'''") == 1 and stripped.count('"""') == 0:
                # Single triple quote - could be opening or closing
                if not in_docstring:
                    in_docstring = True
                else:
                    in_docstring = False
        
        # If we're in a docstring and line has only whitespace, make it empty
        if in_docstring and line and not stripped:
            fixed_lines.append('')
        else:
            fixed_lines.append(line)
    
    fixed_content = '\n'.join(fixed_lines)
    
    # Also fix any trailing whitespace on all lines
    fixed_content = '\n'.join(line.rstrip() for line in fixed_content.split('\n'))
    
    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"Fixed whitespace in {file_path}")

if __name__ == "__main__":
    fix_whitespace("src/henchman/agents/working_memory.py")