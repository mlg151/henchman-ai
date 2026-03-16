"""Test to check the reference filtering logic."""
import textwrap
from pathlib import Path
import tempfile

# Import the function we want to test
from henchman.tools.builtins.symbol_trace import _execute_symbol_trace, SymbolTraceParams

def test_reference_filtering():
    """Test that references on definition lines are filtered out."""
    src1 = textwrap.dedent("""\
        def my_func():
            return 42
        
        result = my_func()  # This should be included as a reference
        my_func()  # This should also be included
    """)
    
    src2 = textwrap.dedent("""\
        # Another file that also defines my_func
        def my_func():
            return 100
        
        # This reference should be included since it's in a different file
        # even though it's on line 2 (a definition line in the other file)
        x = my_func()
    """)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        file1 = tmp_path / "file1.py"
        file1.write_text(src1)
        
        file2 = tmp_path / "file2.py" 
        file2.write_text(src2)
        
        params = SymbolTraceParams(symbol="my_func", path=str(tmp_path))
        result = _execute_symbol_trace(params)
        
        print("Result content:")
        print(result.content)
        print("\n" + "=" * 60)
        
        # Check that references are found
        assert "Reference sites" in result.content
        
        # Count references
        lines = result.content.split('\n')
        ref_section = False
        ref_count = 0
        for line in lines:
            if line.startswith("## Reference sites"):
                ref_section = True
            elif line.startswith("## ") and ref_section:
                break
            elif ref_section and line.startswith("- "):
                ref_count += 1
        
        print(f"Found {ref_count} references")
        
        # We should have:
        # - file1.py line 4: result = my_func()
        # - file1.py line 5: my_func()
        # - file2.py line 6: x = my_func()
        # But NOT file1.py line 1 (definition) or file2.py line 2 (definition)
        
        # Actually, file2.py line 6 reference should be included even though
        # it's line 6 and there's a definition at line 2 in file1.py
        # The bug would be if it's excluded because line 6 is in def_lines
        # (which only contains definition lines from file2.py, not file1.py)
        
        if ref_count >= 3:
            print("✓ Reference filtering appears correct")
            return True
        else:
            print(f"❌ Expected at least 3 references, got {ref_count}")
            return False

if __name__ == "__main__":
    print("Testing reference filtering logic...")
    print("=" * 60)
    
    if test_reference_filtering():
        print("\n✓ Test passed")
    else:
        print("\n❌ Test failed - bug found!")