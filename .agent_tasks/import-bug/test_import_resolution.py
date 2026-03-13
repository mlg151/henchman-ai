#!/usr/bin/env python3
"""Test the import resolution bug."""

from henchman.knowledge.scanner import (
    _build_module_lookup,
    _find_import_target_optimized,
    _path_to_entity_id,
    _path_to_module,
)


def test_import_priority() -> None:
    """Test that imports prioritize exact module > package __init__.py > submodules."""
    # Create test files that demonstrate the bug
    python_files = [
        "foo/__init__.py",      # Should be first choice for "import foo"
        "foo/bar.py",           # Should be second choice for "import foo"
        "foo/baz.py",           # Should be third choice for "import foo"
        "other/foo.py",         # Different foo module in different package
    ]
    
    lookup = _build_module_lookup(python_files)
    
    # Test 1: Importing "foo" should prefer foo/__init__.py over foo/bar.py
    # Currently returns first match which could be foo/bar.py or foo/baz.py
    mod = "foo"
    importing_eid = _path_to_entity_id("test.py")
    
    result = _find_import_target_optimized(mod, importing_eid, lookup)
    
    # The bug: result could be foo-bar-py or foo-baz-py instead of foo---init---py
    print(f"Importing '{mod}' from test.py")
    print(f"Result: {result}")
    print(f"Expected: foo---init---py (foo/__init__.py)")
    
    # Check what we actually got
    if result == "foo---init---py":
        print("✓ Correctly found foo/__init__.py")
    elif result == "foo-bar-py":
        print("✗ Bug: Found foo/bar.py instead of foo/__init__.py")
    elif result == "foo-baz-py":
        print("✗ Bug: Found foo/baz.py instead of foo/__init__.py")
    else:
        print(f"✗ Unexpected result: {result}")


def test_self_import_detection() -> None:
    """Test self-import detection in prefix matching."""
    python_files = [
        "foo/__init__.py",
        "foo/bar.py",
        "foo/baz.py",
    ]
    
    lookup = _build_module_lookup(python_files)
    
    # Test: foo/__init__.py importing "foo" should return None (self-import)
    mod = "foo"
    importing_eid = _path_to_entity_id("foo/__init__.py")
    
    result = _find_import_target_optimized(mod, importing_eid, lookup)
    
    print(f"\nSelf-import test: foo/__init__.py importing '{mod}'")
    print(f"Result: {result}")
    print(f"Expected: None (self-import)")
    
    if result is None:
        print("✓ Correctly detected self-import")
    else:
        print(f"✗ Bug: Found {result} instead of None for self-import")


def test_exact_module_preference() -> None:
    """Test that exact module matches are preferred over prefix matches."""
    python_files = [
        "mymodule.py",          # Exact module
        "package/mymodule.py",  # Package module with same name
    ]
    
    lookup = _build_module_lookup(python_files)
    
    # Importing "mymodule" should prefer mymodule.py over package/mymodule.py
    mod = "mymodule"
    importing_eid = _path_to_entity_id("test.py")
    
    result = _find_import_target_optimized(mod, importing_eid, lookup)
    
    print(f"\nExact module preference test: importing '{mod}'")
    print(f"Result: {result}")
    print(f"Expected: mymodule-py (mymodule.py)")
    
    if result == "mymodule-py":
        print("✓ Correctly found mymodule.py")
    elif result == "package-mymodule-py":
        print("✗ Bug: Found package/mymodule.py instead of mymodule.py")
    else:
        print(f"✗ Unexpected result: {result}")


def test_package_vs_module_conflict() -> None:
    """Test package vs module conflict resolution."""
    python_files = [
        "foo/__init__.py",  # Package foo
        "foo.py",           # Module foo
    ]
    
    lookup = _build_module_lookup(python_files)
    
    # Importing "foo" - which should win? Package or module?
    # Python precedence: module foo.py wins over package foo/__init__.py
    mod = "foo"
    importing_eid = _path_to_entity_id("test.py")
    
    result = _find_import_target_optimized(mod, importing_eid, lookup)
    
    print(f"\nPackage vs module conflict: importing '{mod}'")
    print(f"Result: {result}")
    print(f"Expected: foo-py (foo.py) - module takes precedence over package")
    
    if result == "foo-py":
        print("✓ Correctly found foo.py (module precedence)")
    elif result == "foo---init---py":
        print("✗ Bug: Found foo/__init__.py instead of foo.py")
    else:
        print(f"✗ Unexpected result: {result}")


if __name__ == "__main__":
    print("Testing import resolution bug...")
    print("=" * 60)
    
    test_import_priority()
    test_self_import_detection()
    test_exact_module_preference()
    test_package_vs_module_conflict()
    
    print("=" * 60)
    print("Tests complete.")