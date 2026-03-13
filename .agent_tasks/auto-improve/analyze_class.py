#!/usr/bin/env python3
"""Analyze IntelligentContextManager class structure."""

import ast
import sys

with open("src/henchman/utils/intelligent_context.py", "r") as f:
    content = f.read()

tree = ast.parse(content)

# Find IntelligentContextManager class
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == "IntelligentContextManager":
        print(f"Class: {node.name}")
        print(f"Line range: {node.lineno} - {node.end_lineno}")
        print(f"Number of lines: {node.end_lineno - node.lineno + 1}")
        
        # Count methods
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)
        
        print(f"Number of methods: {len(methods)}")
        print("\nMethods:")
        for i, method in enumerate(methods, 1):
            print(f"  {i:2d}. {method}")
        
        # Group methods by prefix/suffix to identify patterns
        print("\nMethod groups (by prefix):")
        prefixes = {}
        for method in methods:
            if method.startswith("_"):
                # Find the prefix (e.g., "_apply_" from "_apply_intelligent_truncation")
                parts = method.split("_")
                if len(parts) > 2:
                    prefix = "_" + parts[1] + "_"
                else:
                    prefix = method
            else:
                prefix = "public"
            
            prefixes.setdefault(prefix, []).append(method)
        
        for prefix, method_list in sorted(prefixes.items()):
            print(f"  {prefix}: {len(method_list)} methods")
            for method in sorted(method_list):
                print(f"    - {method}")
        
        break