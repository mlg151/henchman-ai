#!/usr/bin/env python3
"""Test the scanner optimization."""

import time
import tempfile
import subprocess
from pathlib import Path

from henchman.knowledge.scanner import (
    _build_module_lookup,
    _find_import_target,
    _find_import_target_optimized,
    _path_to_module,
    _path_to_entity_id,
)


def test_module_lookup() -> None:
    """Test that module lookup works correctly."""
    python_files = [
        "src/foo/bar.py",
        "src/foo/baz.py",
        "tests/test_foo.py",
        "utils/helpers.py",
    ]
    
    lookup = _build_module_lookup(python_files)
    
    # Check that full module names are mapped
    assert lookup["src.foo.bar"] == "src-foo-bar-py"
    assert lookup["src.foo.baz"] == "src-foo-baz-py"
    assert lookup["tests.test_foo"] == "tests-test-foo-py"
    assert lookup["utils.helpers"] == "utils-helpers-py"
    
    # Check that last parts are mapped
    assert lookup["bar"] == "src-foo-bar-py"
    assert lookup["baz"] == "src-foo-baz-py"
    assert lookup["test_foo"] == "tests-test-foo-py"
    assert lookup["helpers"] == "utils-helpers-py"
    
    print("✓ Module lookup test passed")


def test_optimized_vs_naive() -> None:
    """Compare optimized vs naive import matching."""
    # Create test data
    python_files = []
    for i in range(100):
        depth = (i % 3) + 1
        parts = [f"module_{j}" for j in range(depth)]
        parts.append(f"file_{i:04d}")
        path = "/".join(parts) + ".py"
        python_files.append(path)
    
    # Test specific cases - find actual matches
    lookup = _build_module_lookup(python_files)
    
    # Test 1: Simple test with known data
    # Create simpler test data
    simple_files = ["src/foo.py", "src/bar.py", "tests/test_foo.py"]
    simple_lookup = _build_module_lookup(simple_files)
    
    # Import "foo" from bar.py
    mod = "foo"
    importing_eid = _path_to_entity_id("src/bar.py")
    naive_result = _find_import_target(mod, importing_eid, simple_files)
    optimized_result = _find_import_target_optimized(mod, importing_eid, simple_lookup)
    assert naive_result == optimized_result, f"Mismatch for mod={mod}"
    assert naive_result == "src-foo-py", f"Should find src/foo.py"
    
    # Test 2: Self-match should return None
    mod = "foo"
    importing_eid = _path_to_entity_id("src/foo.py")
    naive_result = _find_import_target(mod, importing_eid, simple_files)
    optimized_result = _find_import_target_optimized(mod, importing_eid, simple_lookup)
    assert naive_result == optimized_result, f"Mismatch for self-import mod={mod}"
    assert naive_result is None, f"Self-import should return None"
    
    # Test 3: file_0050 should match module_0.module_1.module_2.file_0050
    mod = "file_0050"
    # Find which file has this as last part
    target_path = None
    for path in python_files:
        if path.endswith("file_0050.py"):
            target_path = path
            break
    assert target_path is not None
    target_eid = _path_to_entity_id(target_path)
    
    # Import from a different file (not the target)
    importing_path = "module_0/file_0000.py"
    importing_eid = _path_to_entity_id(importing_path)
    naive_result = _find_import_target(mod, importing_eid, python_files)
    optimized_result = _find_import_target_optimized(mod, importing_eid, lookup)
    assert naive_result == optimized_result, f"Mismatch for mod={mod}"
    assert naive_result == target_eid, f"Wrong match for {mod}"
    
    print("✓ Optimized vs naive comparison passed")


def benchmark_import_matching() -> None:
    """Benchmark the performance improvement."""
    import random
    
    # Create larger test data
    python_files = []
    for i in range(200):
        depth = random.randint(1, 4)
        parts = [f"pkg_{j}" for j in range(depth)]
        parts.append(f"module_{i:04d}")
        path = "/".join(parts) + ".py"
        python_files.append(path)
    
    # Generate random imports to test
    test_imports = []
    for _ in range(1000):
        file_idx = random.randint(0, len(python_files) - 1)
        file_path = python_files[file_idx]
        file_eid = _path_to_entity_id(file_path)
        
        # Pick a random module to import
        target_idx = random.randint(0, len(python_files) - 1)
        target_path = python_files[target_idx]
        target_module = _path_to_module(target_path)
        
        # Use either full module or last part
        if random.random() > 0.5:
            mod = target_module
        else:
            mod = target_module.split(".")[-1]
        
        test_imports.append((mod, file_eid))
    
    # Benchmark naive approach
    start = time.time()
    naive_results = []
    for mod, file_eid in test_imports:
        result = _find_import_target(mod, file_eid, python_files)
        naive_results.append(result)
    naive_time = time.time() - start
    
    # Benchmark optimized approach
    lookup = _build_module_lookup(python_files)
    start = time.time()
    optimized_results = []
    for mod, file_eid in test_imports:
        result = _find_import_target_optimized(mod, file_eid, lookup)
        optimized_results.append(result)
    optimized_time = time.time() - start
    
    # Verify results match
    assert naive_results == optimized_results, "Results don't match!"
    
    print(f"\nPerformance Benchmark:")
    print(f"  Files: {len(python_files)}")
    print(f"  Import tests: {len(test_imports)}")
    print(f"  Naive time: {naive_time:.4f}s")
    print(f"  Optimized time: {optimized_time:.4f}s")
    print(f"  Speedup: {naive_time/optimized_time:.1f}x")
    
    # Verify significant speedup
    assert optimized_time < naive_time / 10, f"Expected >10x speedup, got {naive_time/optimized_time:.1f}x"
    print("✓ Performance benchmark passed")


def test_edge_cases() -> None:
    """Test edge cases in import matching."""
    python_files = [
        "foo.py",           # module: foo
        "bar/foo.py",       # module: bar.foo (conflict with foo.py)
        "baz/__init__.py",  # module: baz
        "baz/sub/__init__.py",  # module: baz.sub
    ]
    
    lookup = _build_module_lookup(python_files)
    
    # Test cases
    test_cases = [
        # (mod, importing_file, expected_result)
        ("foo", "foo-py", None),  # Self-match should return None
        ("bar.foo", "foo-py", "bar-foo-py"),  # Import bar.foo from foo.py
        ("bar", "bar-foo-py", None),  # No file named bar.py
        ("baz", "baz---init---py", None),  # baz.__init__ doesn't match "baz"
        ("baz.sub", "baz---init---py", "baz-sub---init---py"),  # baz.sub matches baz.sub.__init__
    ]
    
    for mod, importing_file, expected in test_cases:
        result = _find_import_target_optimized(mod, importing_file, lookup)
        assert result == expected, f"Failed for mod={mod}, file={importing_file}: got {result}, expected {expected}"
    
    print("✓ Edge cases test passed")


if __name__ == "__main__":
    print("Running scanner optimization tests...")
    print("=" * 60)
    
    test_module_lookup()
    test_optimized_vs_naive()
    test_edge_cases()
    benchmark_import_matching()
    
    print("=" * 60)
    print("All tests passed! ✓")