#!/usr/bin/env python3
"""Test for the import resolution bug."""

import sys
from pathlib import Path

# Add src to path to import henchman
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from henchman.knowledge.scanner import (
    _build_module_lookup,
    _find_import_target_optimized,
    _path_to_entity_id,
    _path_to_module,
)


def test_import_resolution_bug() -> None:
    """Test the import resolution bug fix.
    
    The bug: When importing "foo", the scanner should prefer foo/__init__.py
    over foo/bar.py or foo/baz.py when multiple files could satisfy the import.
    """
    # Create test files that demonstrate the bug
    python_files = [
        "foo/__init__.py",      # Package foo - should be first choice
        "foo/bar.py",           # Submodule - should be second choice  
        "foo/baz.py",           # Another submodule - third choice
        "other/foo.py",         # Different foo module in different package
    ]
    
    module_to_eid, eid_to_module = _build_module_lookup(python_files)
    
    # Test 1: External file importing "foo" should find foo/__init__.py
    # (not foo/bar.py or foo/baz.py arbitrarily)
    mod = "foo"
    importing_eid = _path_to_entity_id("external.py")
    importing_module = None  # External file not in repo
    
    result = _find_import_target_optimized(
        mod, importing_eid, importing_module, module_to_eid, eid_to_module
    )
    
    expected = _path_to_entity_id("foo/__init__.py")
    assert result == expected, (
        f"Importing '{mod}' should find foo/__init__.py, got {result}"
    )
    print(f"✓ External import of '{mod}' correctly finds foo/__init__.py")
    
    # Test 2: foo/bar.py importing "foo" should find foo/__init__.py
    # (not foo.py or other/foo.py)
    mod = "foo"
    importing_eid = _path_to_entity_id("foo/bar.py")
    importing_module = _path_to_module("foo/bar.py")
    
    result = _find_import_target_optimized(
        mod, importing_eid, importing_module, module_to_eid, eid_to_module
    )
    
    expected = _path_to_entity_id("foo/__init__.py")
    assert result == expected, (
        f"foo/bar.py importing '{mod}' should find foo/__init__.py, got {result}"
    )
    print(f"✓ foo/bar.py importing '{mod}' correctly finds foo/__init__.py")
    
    # Test 3: Self-import detection
    # foo/__init__.py importing "foo" should be None (self-import)
    mod = "foo"
    importing_eid = _path_to_entity_id("foo/__init__.py")
    importing_module = _path_to_module("foo/__init__.py")
    
    result = _find_import_target_optimized(
        mod, importing_eid, importing_module, module_to_eid, eid_to_module
    )
    
    assert result is None, (
        f"foo/__init__.py importing '{mod}' should be self-import (None), got {result}"
    )
    print(f"✓ foo/__init__.py importing '{mod}' correctly detected as self-import")
    
    # Test 4: Module takes precedence over package when both exist
    python_files2 = [
        "foo.py",              # Module foo
        "foo/__init__.py",     # Package foo
    ]
    
    module_to_eid2, eid_to_module2 = _build_module_lookup(python_files2)
    
    mod = "foo"
    importing_eid = _path_to_entity_id("external.py")
    importing_module = None
    
    result = _find_import_target_optimized(
        mod, importing_eid, importing_module, module_to_eid2, eid_to_module2
    )
    
    expected = _path_to_entity_id("foo.py")
    assert result == expected, (
        f"Module foo.py should take precedence over package foo/__init__.py, got {result}"
    )
    print(f"✓ Module foo.py correctly takes precedence over package foo/__init__.py")
    
    print("\n✅ All import resolution bug tests passed!")


if __name__ == "__main__":
    print("Testing import resolution bug fix...")
    print("=" * 60)
    test_import_resolution_bug()
    print("=" * 60)