#!/usr/bin/env python3
"""Check duplicate code claims."""

import ast
import sys

with open("src/henchman/utils/intelligent_context.py", "r") as f:
    content = f.read()

tree = ast.parse(content)

# Find methods mentioned in smells
methods_to_check = [
    ("_count_tokens", 2292),
    ("_calculate_importance_scores", 2700),  # Actually starts around 2700
    ("_calculate_cluster_importance", 2785),  # Actually starts around 2785
    ("_preserve_critical_context", 2835),  # Actually starts around 2835
    ("validate_compacted_sequence", 2683),  # In IntelligentContextManager
]

# Actually, let me just print the methods
print("Checking methods mentioned in duplicate code smells:")
print("=" * 60)

# Get all function definitions
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        if node.name in ["_count_tokens", "_calculate_importance_scores", 
                        "_calculate_cluster_importance", "_preserve_critical_context",
                        "validate_compacted_sequence"]:
            # Get method source
            start_line = node.lineno
            end_line = node.end_lineno
            lines = content.splitlines()[start_line-1:end_line]
            
            print(f"\n{node.name} (lines {start_line}-{end_line}):")
            print("-" * 40)
            # Print just the signature and first few lines
            for i, line in enumerate(lines[:10]):
                print(f"  {line}")
            if len(lines) > 10:
                print(f"  ... and {len(lines) - 10} more lines")
            
            # Count lines of actual code (not empty/comments at start)
            code_lines = 0
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith('"""'):
                    code_lines += 1
            
            print(f"  Total lines: {len(lines)}, Code lines: {code_lines}")