#!/usr/bin/env python3
"""Test to identify missing type hints in textual_widgets.py"""

import ast
import inspect
from typing import Any, get_type_hints
import sys
from pathlib import Path

def check_function_type_hints(func) -> list[str]:
    """Check if a function has complete type hints."""
    issues = []
    
    try:
        # Get type hints
        hints = get_type_hints(func)
        sig = inspect.signature(func)
        
        # Check parameters
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue  # self doesn't need type hint
            
            if param.annotation == inspect.Parameter.empty:
                issues.append(f"Parameter '{param_name}' missing type hint")
        
        # Check return type
        if sig.return_annotation == inspect.Signature.empty:
            issues.append("Missing return type hint")
    
    except (ValueError, TypeError) as e:
        issues.append(f"Error checking type hints: {e}")
    
    return issues

def check_file_type_hints(filepath: str) -> dict[str, list[str]]:
    """Check all functions in a file for missing type hints."""
    issues = {}
    
    # Read and parse the file
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Parse AST
    tree = ast.parse(content)
    
    # Find all function and method definitions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = node.name
            
            # Check if it's a method (has 'self' as first arg)
            is_method = (node.args.args and node.args.args[0].arg == 'self')
            
            # Skip private methods starting with underscore (except __init__)
            if func_name.startswith('_') and func_name != '__init__':
                continue
            
            # Check parameters
            func_issues = []
            
            # Check all parameters except 'self'
            for arg in node.args.args:
                if arg.arg == 'self':
                    continue
                if arg.annotation is None:
                    func_issues.append(f"Parameter '{arg.arg}' missing type hint")
            
            # Check *args and **kwargs
            if node.args.vararg and node.args.vararg.annotation is None:
                func_issues.append(f"Parameter '*{node.args.vararg.arg}' missing type hint")
            if node.args.kwarg and node.args.kwarg.annotation is None:
                func_issues.append(f"Parameter '**{node.args.kwarg.arg}' missing type hint")
            
            # Check return type
            if node.returns is None:
                func_issues.append("Missing return type hint")
            
            if func_issues:
                issues[func_name] = func_issues
    
    return issues

if __name__ == "__main__":
    filepath = "src/henchman/cli/textual_widgets.py"
    issues = check_file_type_hints(filepath)
    
    if issues:
        print(f"Type hint issues in {filepath}:")
        for func_name, func_issues in issues.items():
            print(f"\n{func_name}:")
            for issue in func_issues:
                print(f"  - {issue}")
        sys.exit(1)
    else:
        print(f"No type hint issues found in {filepath}")
        sys.exit(0)