#!/usr/bin/env python3
"""Analyze missing type hints in textual_widgets.py"""

import ast
import sys
from pathlib import Path

def analyze_file(filepath: Path) -> None:
    """Analyze a Python file for missing type hints."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    tree = ast.parse(content)
    
    print(f"Analyzing {filepath}")
    print("=" * 80)
    
    # Track methods with missing type hints
    methods_without_hints = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check if function has return type annotation
            has_return_type = node.returns is not None
            
            # Check parameters for type hints
            params_without_hints = []
            total_params = 0
            
            # Check positional-only args
            for arg in node.args.posonlyargs:
                total_params += 1
                if arg.annotation is None:
                    params_without_hints.append(arg.arg)
            
            # Check args
            for arg in node.args.args:
                total_params += 1
                if arg.annotation is None:
                    params_without_hints.append(arg.arg)
            
            # Check vararg
            if node.args.vararg:
                total_params += 1
                if node.args.vararg.annotation is None:
                    params_without_hints.append(node.args.vararg.arg)
            
            # Check kwonlyargs
            for arg in node.args.kwonlyargs:
                total_params += 1
                if arg.annotation is None:
                    params_without_hints.append(arg.arg)
            
            # Check kwarg
            if node.args.kwarg:
                total_params += 1
                if node.args.kwarg.annotation is None:
                    params_without_hints.append(node.args.kwarg.arg)
            
            # Skip __init__ methods that only have **kwargs
            if node.name == '__init__':
                has_kwargs_only = (
                    len(node.args.args) == 1 and 
                    node.args.args[0].arg == 'self' and
                    node.args.vararg is None and
                    len(node.args.kwonlyargs) == 0 and
                    node.args.kwarg is not None
                )
                if has_kwargs_only:
                    continue
            
            # Skip methods with no parameters (except self)
            if total_params <= 1:  # Only self
                continue
            
            if params_without_hints or not has_return_type:
                methods_without_hints.append({
                    'name': node.name,
                    'line': node.lineno,
                    'missing_params': params_without_hints,
                    'missing_return': not has_return_type,
                    'total_params': total_params
                })
    
    # Print results
    if not methods_without_hints:
        print("✓ All methods have complete type hints!")
        return
    
    print(f"Found {len(methods_without_hints)} methods with missing type hints:\n")
    
    for method in methods_without_hints:
        print(f"Line {method['line']}: {method['name']}")
        if method['missing_params']:
            print(f"  Missing parameter hints: {', '.join(method['missing_params'])}")
        if method['missing_return']:
            print(f"  Missing return type hint")
        print()

if __name__ == '__main__':
    filepath = Path("src/henchman/cli/textual_widgets.py")
    if filepath.exists():
        analyze_file(filepath)
    else:
        print(f"File not found: {filepath}")
        sys.exit(1)