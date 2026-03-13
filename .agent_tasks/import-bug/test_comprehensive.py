#!/usr/bin/env python3
"""Comprehensive test of import resolution."""

import sys
from pathlib import Path

# Add src to path to import henchman
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from henchman.knowledge.scanner import (
    _build_module_lookup,
    _find_import_target,
    _find_import_target_optimized,
    _path_to_entity_id,
    _path_to_module,
)


def test_build_module_lookup() -> None:
    """Test how module lookup is built."""
    print("Testing _build_module_lookup...")
    
    python_files = [
        "foo.py",              # Module foo
        "foo/__init__.py",     # Package foo
        "foo/bar.py",          # Submodule foo.bar
        "foo/baz/__init__.py", # Subpackage foo.baz
        "foo/baz/qux.py",      # Submodule foo.baz.qux
        "other/foo.py",        # Module other.foo (conflict)
    ]
    
    module_to_eid, eid_to_module = _build_module_lookup(python_files)
    
    print("\nLookup entries:")
    for key in sorted(module_to_eid.keys()):
        print(f"  '{key}' -> {module_to_eid[key]}")
    
    # Check specific mappings
    print("\nKey analysis:")
    print(f"  'foo' maps to: {module_to_eid.get('foo')}")
    print(f"  'foo.__init__' maps to: {module_to_eid.get('foo.__init__')}")
    print(f"  'foo.bar' maps to: {module_to_eid.get('foo.bar')}")
    print(f"  'bar' maps to: {module_to_eid.get('bar')}")
    print(f"  'foo.baz' maps to: {module_to_eid.get('foo.baz')}")
    print(f"  'baz' maps to: {module_to_eid.get('baz')}")
    print(f"  'foo.baz.qux' maps to: {module_to_eid.get('foo.baz.qux')}")
    print(f"  'qux' maps to: {module_to_eid.get('qux')}")
    print(f"  'other.foo' maps to: {module_to_eid.get('other.foo')}")
    
    # The bug: 'foo' should map to foo.py (module) or foo/__init__.py (package)
    # but currently maps to other.foo because that's the first file where last_part = "foo"


def test_import_scenarios() -> None:
    """Test various import scenarios."""
    print("\n\nTesting import scenarios...")
    
    python_files = [
        "foo.py",              # Module foo
        "foo/__init__.py",     # Package foo  
        "foo/bar.py",          # Submodule foo.bar
        "other/foo.py",        # Module other.foo
    ]
    
    module_to_eid, eid_to_module = _build_module_lookup(python_files)
    
    test_cases = [
        # (importing_file, mod_to_import, expected_target, description)
        ("test.py", "foo", "foo-py", "import foo should find foo.py (module)"),
        ("test.py", "foo.bar", "foo-bar-py", "import foo.bar should find foo/bar.py"),
        ("test.py", "bar", "foo-bar-py", "import bar should find foo/bar.py"),
        ("foo.py", "foo", None, "foo.py importing foo should be self-import"),
        ("foo/__init__.py", "foo", None, "foo/__init__.py importing foo should be self-import"),
        ("foo/bar.py", "foo", "foo---init---py", "foo/bar.py importing foo should find foo/__init__.py"),
        ("foo/bar.py", "bar", None, "foo/bar.py importing bar should be self-import"),
        ("other/foo.py", "foo", "foo-py", "other/foo.py importing foo should find foo.py"),
    ]
    
    for importing_file, mod, expected, description in test_cases:
        importing_eid = _path_to_entity_id(importing_file)
        importing_module = _path_to_module(importing_file) if importing_file != "test.py" else None
        result = _find_import_target_optimized(
            mod, importing_eid, importing_module, module_to_eid, eid_to_module
        )
        
        status = "✓" if result == expected else "✗"
        print(f"{status} {description}")
        print(f"  Importing '{mod}' from {importing_file}")
        print(f"  Expected: {expected}, Got: {result}")
        if result != expected:
            print(f"  BUG!")


def test_prefix_matching() -> None:
    """Test prefix matching for submodules."""
    print("\n\nTesting prefix matching...")
    
    python_files = [
        "mypkg/__init__.py",
        "mypkg/submod.py",
        "mypkg/nested/__init__.py",
        "mypkg/nested/deep.py",
    ]
    
    module_to_eid, eid_to_module = _build_module_lookup(python_files)
    
    test_cases = [
        # (importing_file, mod_to_import, expected_target, description)
        ("test.py", "mypkg", "mypkg---init---py", "import mypkg should find mypkg/__init__.py"),
        ("test.py", "mypkg.submod", "mypkg-submod-py", "import mypkg.submod should find mypkg/submod.py"),
        ("test.py", "submod", "mypkg-submod-py", "import submod should find mypkg/submod.py"),
        ("test.py", "mypkg.nested", "mypkg-nested---init---py", "import mypkg.nested should find mypkg/nested/__init__.py"),
        ("test.py", "nested", "mypkg-nested---init---py", "import nested should find mypkg/nested/__init__.py"),
        ("test.py", "mypkg.nested.deep", "mypkg-nested-deep-py", "import mypkg.nested.deep should find mypkg/nested/deep.py"),
        ("test.py", "deep", "mypkg-nested-deep-py", "import deep should find mypkg/nested/deep.py"),
    ]
    
    for importing_file, mod, expected, description in test_cases:
        importing_eid = _path_to_entity_id(importing_file)
        importing_module = _path_to_module(importing_file) if importing_file != "test.py" else None
        result = _find_import_target_optimized(
            mod, importing_eid, importing_module, module_to_eid, eid_to_module
        )
        
        status = "✓" if result == expected else "✗"
        print(f"{status} {description}")
        if result != expected:
            print(f"  Expected: {expected}, Got: {result}")
            print(f"  BUG!")


def test_self_import_edge_cases() -> None:
    """Test edge cases for self-import detection."""
    print("\n\nTesting self-import edge cases...")
    
    python_files = [
        "foo.py",
        "bar/foo.py",
        "baz/__init__.py",
    ]
    
    module_to_eid, eid_to_module = _build_module_lookup(python_files)
    
    test_cases = [
        # (importing_file, mod_to_import, expected_target, description)
        ("foo.py", "foo", None, "foo.py importing foo = self"),
        ("foo.py", "bar.foo", "bar-foo-py", "foo.py importing bar.foo = different"),
        ("bar/foo.py", "foo", None, "bar/foo.py importing foo = self (last part matches)"),
        ("bar/foo.py", "bar.foo", None, "bar/foo.py importing bar.foo = self (full match)"),
        ("baz/__init__.py", "baz", None, "baz/__init__.py importing baz = self (package)"),
        ("baz/__init__.py", "baz.__init__", None, "baz/__init__.py importing baz.__init__ = self"),
    ]
    
    for importing_file, mod, expected, description in test_cases:
        importing_eid = _path_to_entity_id(importing_file)
        importing_module = _path_to_module(importing_file)
        result = _find_import_target_optimized(
            mod, importing_eid, importing_module, module_to_eid, eid_to_module
        )
        
        status = "✓" if result == expected else "✗"
        print(f"{status} {description}")
        if result != expected:
            print(f"  Expected: {expected}, Got: {result}")
            print(f"  BUG!")


if __name__ == "__main__":
    print("Comprehensive import resolution tests")
    print("=" * 70)
    
    test_build_module_lookup()
    test_import_scenarios()
    test_prefix_matching()
    test_self_import_edge_cases()
    
    print("\n" + "=" * 70)
    print("Tests complete.")