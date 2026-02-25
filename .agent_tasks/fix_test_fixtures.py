#!/usr/bin/env python3
"""Fix test fixtures to patch correct import path."""

import sys
from pathlib import Path


def main():
    file_path = Path("tests/cli/test_repl.py")
    content = file_path.read_text()

    # Replace all occurrences
    old = 'patch("henchman.cli.repl.create_session")'
    new = 'patch("henchman.cli.input.create_session")'

    if old not in content:
        print(f"Error: Could not find {old} in file")
        return 1

    new_content = content.replace(old, new)
    file_path.write_text(new_content)
    print(f"Replaced {old} with {new}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
