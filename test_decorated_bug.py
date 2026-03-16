"""Test to demonstrate the decorated function signature bug."""
import ast
import textwrap
from pathlib import Path
import tempfile

# Import the function we want to test
from henchman.tools.builtins.symbol_trace import _find_definitions_in_file

def test_decorated_function_signature_bug():
    """Test that demonstrates the bug with decorated function signatures."""
    src = textwrap.dedent("""\
        from typing import Optional
        
        @decorator
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
        
        # The bug: signature should be "def decorated_func(x: int) -> Optional[str]:"
        # But currently returns "@decorator"
        assert len(defs) == 1
        assert defs[0].kind == "function"
        
        # This is the critical assertion that should fail with the bug
        # The signature should NOT be just the decorator
        assert defs[0].signature != "@decorator", f"Signature is just decorator: '{defs[0].signature}'"
        
        # The signature should contain the function definition
        assert "def decorated_func" in defs[0].signature
        assert "x: int" in defs[0].signature or "(x: int)" in defs[0].signature
        assert "-> Optional[str]" in defs[0].signature
        
        print("✓ Test passed - signature correctly extracted")
    
    file_path.unlink()

if __name__ == "__main__":
    test_decorated_function_signature_bug()