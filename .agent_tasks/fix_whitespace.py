#!/usr/bin/env python3
"""Fix whitespace in blank lines within docstrings."""

import re
from pathlib import Path

def fix_docstring_whitespace(file_path: Path) -> None:
    """Fix whitespace in blank lines within docstrings."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern to find docstrings (triple quotes) and fix blank lines with whitespace inside them
    lines = content.splitlines(keepends=True)
    in_docstring = False
    docstring_quotes = None
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # Check if we're entering/exiting a docstring
        stripped = line.lstrip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if not in_docstring:
                # Entering docstring
                in_docstring = True
                docstring_quotes = stripped[:3]
            elif line.rstrip().endswith(docstring_quotes):
                # Exiting docstring
                in_docstring = False
                docstring_quotes = None
        
        # If we're in a docstring and line is blank with whitespace, fix it
        if in_docstring and line.strip() == '' and line != '\n':
            # Replace with just newline
            fixed_lines.append('\n')
        else:
            fixed_lines.append(line)
    
    fixed_content = ''.join(fixed_lines)
    
    if fixed_content != content:
        with open(file_path, 'w') as f:
            f.write(fixed_content)
        print(f"Fixed whitespace in {file_path}")
    else:
        print(f"No changes needed for {file_path}")

if __name__ == "__main__":
    file_path = Path("src/henchman/agents/working_memory.py")
    fix_docstring_whitespace(file_path)