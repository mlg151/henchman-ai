#!/usr/bin/env python3
"""Fix import ordering in orchestrator.py."""

import sys
from pathlib import Path


def main():
    file_path = Path("src/henchman/agents/orchestrator.py")
    content = file_path.read_text()

    # Split the file into parts
    lines = content.splitlines()

    # Find the first import block (lines 1-5)
    # Find the Metrics class start
    metrics_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("class Metrics"):
            metrics_start = i
            break

    if metrics_start is None:
        print("Error: Could not find Metrics class")
        return 1

    # Find the imports after Metrics class
    imports_start = None
    for i in range(metrics_start, len(lines)):
        if "from henchman.agents.ledger import TaskLedger" in lines[i]:
            imports_start = i
            break

    if imports_start is None:
        print("Error: Could not find imports after Metrics class")
        return 1

    # Find where these imports end (before the constants)
    imports_end = None
    for i in range(imports_start, len(lines)):
        if lines[i].strip().startswith("# Interval"):
            imports_end = i
            break

    if imports_end is None:
        print("Error: Could not find end of imports")
        return 1

    # Extract the parts
    header = lines[:metrics_start]  # Includes initial imports
    metrics_class = lines[metrics_start:imports_start]
    imports = lines[imports_start:imports_end]
    rest = lines[imports_end:]

    # Reorder: header (with initial imports) + imports + metrics_class + rest
    new_lines = header + imports + metrics_class + rest

    # Write back
    file_path.write_text("\n".join(new_lines) + "\n")
    print("Fixed import ordering in orchestrator.py")
    return 0

if __name__ == "__main__":
    sys.exit(main())
