"""Test to demonstrate the decorated function signature bug with multiple decorators."""
import ast
import textwrap
from pathlib import Path
import tempfile

# Import the function we want to test
from henchman.tools.builtins.symbol_trace import _find_definitions_in_file

def test_decorated_function_with_multiple_decorators():
    """Test with multiple decorators on separate lines."""
    src = textwrap.dedent("""\
        from typing import Optional
        
        @decorator1
        @decorator2
        @decorator3(arg1, arg2)
        def decorated_func(x: int) -> Optional[str]:
            return str(x) if x > 0 else None
    """)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(src)
        f.flush()
        file_path = Path(f.name)
        
        defs = _find_definitions_in_file(file_path, "decorated_func")
        
        print(f"Found {len(defs)} definitions")
        for d in defs:
            print(f"  Kind: {d.kind}, Signature: '{d.signature}'")
        
        assert len(defs) == 1
        assert defs[0].kind == "function"
        
        # Check the signature
        signature = defs[0].signature
        print(f"\nSignature: '{signature}'")
        
        # The bug might be that it returns "@decorator1" or similar
        if signature.startswith("@"):
            print(f"❌ BUG CONFIRMED: Signature starts with decorator: '{signature}'")
            print("   Expected: 'def decorated_func(x: int) -> Optional[str]:'")
            return False
        else:
            print("✓ Signature correctly starts with 'def'")
            return True
    
    file_path.unlink()

def test_decorated_function_with_inline_decorators():
    """Test with decorators on the same line as function."""
    src = textwrap.dedent("""\
        from typing import Optional
        
        @decorator
        def decorated_func(x: int) -> Optional[str]: return str(x) if x > 0 else None
    """)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(src)
        f.flush()
        file_path = Path(f.name)
        
        defs = _find_definitions_in_file(file_path, "decorated_func")
        
        print(f"\nTest 2 - Inline decorator:")
        print(f"Found {len(defs)} definitions")
        for d in defs:
            print(f"  Kind: {d.kind}, Signature: '{d.signature}'")
        
        assert len(defs) == 1
        signature = defs[0].signature
        print(f"Signature: '{signature}'")
        
        if signature.startswith("@"):
            print(f"❌ BUG: Signature starts with decorator: '{signature}'")
            return False
        else:
            print("✓ Signature correctly starts with 'def'")
            return True
    
    file_path.unlink()

if __name__ == "__main__":
    print("Testing decorated function signature extraction...")
    print("=" * 60)
    
    result1 = test_decorated_function_with_multiple_decorators()
    result2 = test_decorated_function_with_inline_decorators()
    
    print("\n" + "=" * 60)
    if result1 and result2:
        print("✓ All tests passed - no bug found")
    else:
        print("❌ Bug found in decorated function signature extraction")