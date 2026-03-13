#!/usr/bin/env python3
"""Analyze type hints in ledger.py to identify missing annotations."""

import ast
from pathlib import Path

def analyze_file(file_path: Path) -> None:
    """Analyze a Python file for missing type hints."""
    content = file_path.read_text()
    tree = ast.parse(content)
    
    print(f"Analyzing {file_path}")
    print("=" * 80)
    
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Get line number
            start_line = node.lineno
            func_name = node.name
            
            # Check return type annotation
            returns_annotation = bool(node.returns)
            
            # Check args annotations
            args_without_annotations = []
            for arg in node.args.args:
                if arg.arg != 'self' and not arg.annotation:
                    args_without_annotations.append(arg.arg)
            
            # Check for *args and **kwargs annotations
            if node.args.vararg and not node.args.vararg.annotation:
                args_without_annotations.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg and not node.args.kwarg.annotation:
                args_without_annotations.append(f"**{node.args.kwarg.arg}")
            
            total_args = len([a for a in node.args.args if a.arg != 'self'])
            if node.args.vararg:
                total_args += 1
            if node.args.kwarg:
                total_args += 1
            
            functions.append({
                'name': func_name,
                'line': start_line,
                'returns_annotated': returns_annotation,
                'args_missing_annotations': args_without_annotations,
                'total_args': total_args
            })
    
    # Print results
    print(f"{'Line':<5} {'Function':<30} {'Returns':<8} {'Missing Args':<40}")
    print(f"{'-'*5} {'-'*30} {'-'*8} {'-'*40}")
    
    for func in functions:
        missing_str = ", ".join(func['args_missing_annotations']) if func['args_missing_annotations'] else "None"
        returns_str = "Yes" if func['returns_annotated'] else "NO"
        print(f"{func['line']:<5} {func['name']:<30} {returns_str:<8} {missing_str:<40}")
    
    # Summary
    total_functions = len(functions)
    functions_with_return = sum(1 for f in functions if f['returns_annotated'])
    functions_with_all_args = sum(1 for f in functions if not f['args_missing_annotations'])
    
    print("\n" + "=" * 80)
    print(f"SUMMARY:")
    print(f"  Total functions: {total_functions}")
    print(f"  Functions with return type: {functions_with_return}/{total_functions} ({functions_with_return/total_functions*100:.1f}%)")
    print(f"  Functions with all args typed: {functions_with_all_args}/{total_functions} ({functions_with_all_args/total_functions*100:.1f}%)")

if __name__ == "__main__":
    analyze_file(Path("src/henchman/agents/ledger.py"))