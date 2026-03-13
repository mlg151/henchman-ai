#!/usr/bin/env python3
"""Analyze lines in IntelligentContextManager."""

import ast
import sys

with open("src/henchman/utils/intelligent_context.py", "r") as f:
    content = f.read()
    lines = content.splitlines()

tree = ast.parse(content)

# Find IntelligentContextManager class
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == "IntelligentContextManager":
        start_line = node.lineno - 1  # Convert to 0-indexed
        end_line = node.end_lineno - 1
        
        class_lines = lines[start_line:end_line + 1]
        
        # Count different types of lines
        total_lines = len(class_lines)
        code_lines = 0
        comment_lines = 0
        docstring_lines = 0
        blank_lines = 0
        
        in_docstring = False
        for line in class_lines:
            stripped = line.strip()
            
            # Check for docstrings (triple quotes)
            if '"""' in line or "'''" in line:
                if not in_docstring:
                    in_docstring = True
                    docstring_lines += 1
                else:
                    in_docstring = False
                    docstring_lines += 1
                continue
            
            if in_docstring:
                docstring_lines += 1
            elif stripped == "":
                blank_lines += 1
            elif stripped.startswith("#"):
                comment_lines += 1
            else:
                code_lines += 1
        
        print(f"Analysis of IntelligentContextManager class:")
        print(f"  Total lines: {total_lines}")
        print(f"  Code lines: {code_lines} ({code_lines/total_lines*100:.1f}%)")
        print(f"  Docstring lines: {docstring_lines} ({docstring_lines/total_lines*100:.1f}%)")
        print(f"  Comment lines: {comment_lines} ({comment_lines/total_lines*100:.1f}%)")
        print(f"  Blank lines: {blank_lines} ({blank_lines/total_lines*100:.1f}%)")
        
        # Also count methods and their average length
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_len = item.end_lineno - item.lineno + 1
                methods.append((item.name, method_len))
        
        print(f"\nMethod statistics:")
        print(f"  Number of methods: {len(methods)}")
        if methods:
            avg_len = sum(m[1] for m in methods) / len(methods)
            max_len = max(m[1] for m in methods)
            max_method = max(methods, key=lambda x: x[1])
            min_len = min(m[1] for m in methods)
            min_method = min(methods, key=lambda x: x[1])
            
            print(f"  Average method length: {avg_len:.1f} lines")
            print(f"  Longest method: {max_method[0]} ({max_len} lines)")
            print(f"  Shortest method: {min_method[0]} ({min_len} lines)")
            
            # Show methods longer than 30 lines (Long Method smell)
            long_methods = [(name, length) for name, length in methods if length > 30]
            if long_methods:
                print(f"\n  Long methods (>30 lines):")
                for name, length in sorted(long_methods, key=lambda x: x[1], reverse=True):
                    print(f"    - {name}: {length} lines")
        
        break