"""Test the annotation collection bug."""
import textwrap
from pathlib import Path
import tempfile

# Import the function we want to test
from henchman.tools.builtins.symbol_trace import _collect_annotations

def test_missing_annotation_types():
    """Test that annotations in posonlyargs, vararg, and kwarg are collected."""
    src = textwrap.dedent("""\
        from typing import Tuple, Dict
        
        def example_func(
            pos_only: int, /,
            normal: str,
            *args: Tuple[int, ...],
            kw_only: float = 0.0,
            **kwargs: Dict[str, bool],
        ) -> None:
            pass
        
        # Also test AnnAssign
        x: int = 5
        y: str = "hello"
    """)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(src)
        f.flush()
        file_path = Path(f.name)
        
        # Test collecting annotations for "int"
        int_annotations = _collect_annotations([file_path], "int")
        print(f"Annotations containing 'int': {int_annotations}")
        
        # Test collecting annotations for "str"  
        str_annotations = _collect_annotations([file_path], "str")
        print(f"Annotations containing 'str': {str_annotations}")
        
        # Test collecting annotations for "Tuple"
        tuple_annotations = _collect_annotations([file_path], "Tuple")
        print(f"Annotations containing 'Tuple': {tuple_annotations}")
        
        # Test collecting annotations for "Dict"
        dict_annotations = _collect_annotations([file_path], "Dict")
        print(f"Annotations containing 'Dict': {dict_annotations}")
        
        # The bug: pos_only: int should be found, *args: Tuple should be found, **kwargs: Dict should be found
        # But currently only normal: str and kw_only: float will be found
        
        expected_for_int = ["int"]  # pos_only: int and x: int
        expected_for_str = ["str"]  # normal: str and y: str
        expected_for_tuple = ["Tuple[int, ...]"]  # *args: Tuple[int, ...]
        expected_for_dict = ["Dict[str, bool]"]  # **kwargs: Dict[str, bool]
        
        print("\n" + "=" * 60)
        print("Checking for bug...")
        
        all_found = True
        
        # Check int annotations
        if not any("int" in ann for ann in int_annotations):
            print("❌ Bug: 'int' annotations not found (should include pos_only: int)")
            all_found = False
        else:
            print("✓ 'int' annotations found")
            
        # Check Tuple annotations
        if not any("Tuple" in ann for ann in tuple_annotations):
            print("❌ Bug: 'Tuple' annotations not found (should include *args: Tuple[int, ...])")
            all_found = False
        else:
            print("✓ 'Tuple' annotations found")
            
        # Check Dict annotations
        if not any("Dict" in ann for ann in dict_annotations):
            print("❌ Bug: 'Dict' annotations not found (should include **kwargs: Dict[str, bool])")
            all_found = False
        else:
            print("✓ 'Dict' annotations found")
        
        if all_found:
            print("\n✓ All annotations found - bug might be fixed?")
        else:
            print("\n❌ Bug confirmed: missing annotations!")
            
        return all_found
    
    file_path.unlink()

if __name__ == "__main__":
    print("Testing annotation collection for all argument types...")
    print("=" * 60)
    
    test_missing_annotation_types()