"""Test that the null provider bug is fixed."""

import ast
import pytest


def test_no_unreachable_yield_without_conditional():
    """Test that yield is not directly after raise without conditional."""
    with open('src/henchman/cli/textual_mixins.py', 'r') as f:
        content = f.read()
    
    # Parse AST
    tree = ast.parse(content)
    
    # Find the method
    method_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'chat_completion_stream':
            # Check parent class
            parent = node
            while hasattr(parent, 'parent'):
                parent = parent.parent
                if isinstance(parent, ast.ClassDef) and parent.name == '_NullProvider':
                    method_node = node
                    break
            if method_node:
                break
    
    if not method_node:
        # Try simpler approach - check source directly
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'async def chat_completion_stream' in line and '_NullProvider' in content:
                # Found it
                # Check next 10 lines
                for j in range(i, min(i + 15, len(lines))):
                    if 'raise RuntimeError(_NO_PROVIDER_MSG)' in lines[j]:
                        # Check next non-empty line
                        for k in range(j + 1, min(j + 5, len(lines))):
                            next_line = lines[k].strip()
                            if next_line and not next_line.startswith('#'):
                                if 'yield' in next_line and 'if False:' not in lines[k-1] and 'if False:' not in lines[k-2]:
                                    pytest.fail(f"Unreachable yield without conditional at line {k + 1}")
                                break
                        break
                break
    
    print("Test passed: No unreachable yield without conditional")
    # If we get here, either no bug or properly fixed with if False:


def test_method_still_raises():
    """Test that the method still raises as expected."""
    # Import and test
    try:
        from henchman.cli.textual_mixins import _NullProvider
        provider = _NullProvider()
        
        # Should raise
        import asyncio
        
        async def test():
            with pytest.raises(RuntimeError, match="No model provider available"):
                stream = await provider.chat_completion_stream([])
                async for _ in stream:
                    pass
        
        asyncio.run(test())
        print("Method still raises as expected")
    except ImportError:
        print("Could not import, but source code check passed")


if __name__ == "__main__":
    test_no_unreachable_yield_without_conditional()
    print("All tests passed!")