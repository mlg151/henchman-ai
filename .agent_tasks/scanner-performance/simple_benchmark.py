#!/usr/bin/env python3
"""Simple benchmark focusing on algorithmic complexity."""

import time
import random
from typing import List, Tuple

# Simulate the _find_import_target function behavior
def find_import_target_naive(mod: str, file_eid: str, python_files: List[str]) -> str | None:
    """Current O(n) implementation per import."""
    for other_path in python_files:
        # Simplified version of the logic
        other_module = other_path.replace("/", ".").replace("\\", ".").removesuffix(".py")
        if other_module.split(".")[-1] == mod or other_module.startswith(mod):
            other_eid = other_path.lower().replace("/", "-").replace("\\", "-").replace(".", "-").replace("_", "-").rstrip("-")
            if other_eid != file_eid:
                return other_eid
            break
    return None

def find_import_target_optimized(mod: str, lookup_dict: dict, file_eid: str) -> str | None:
    """Optimized O(1) implementation using precomputed lookup."""
    # Try exact module name match first
    if mod in lookup_dict:
        target = lookup_dict[mod]
        if target != file_eid:
            return target
    
    # Try module as prefix (for submodules)
    for key, value in lookup_dict.items():
        if key.startswith(mod) and value != file_eid:
            return value
    
    return None

def benchmark_import_matching(num_files: int = 100, imports_per_file: int = 5) -> Tuple[float, float]:
    """Benchmark naive vs optimized import matching."""
    
    # Generate test data
    python_files = []
    for i in range(num_files):
        depth = random.randint(1, 3)
        parts = [f"module_{j}" for j in range(depth)]
        parts.append(f"file_{i:04d}")
        path = "/".join(parts) + ".py"
        python_files.append(path)
    
    # Generate imports
    imports_by_file = []
    for i in range(num_files):
        file_imports = []
        for _ in range(imports_per_file):
            # Import random modules
            target_idx = random.randint(0, num_files - 1)
            if target_idx != i:
                target_path = python_files[target_idx]
                target_module = target_path.replace("/", ".").replace("\\", ".").removesuffix(".py")
                # Use last part or full module
                if random.random() > 0.5:
                    mod = target_module.split(".")[-1]
                else:
                    mod = target_module
                file_imports.append(mod)
        imports_by_file.append(file_imports)
    
    # Benchmark naive approach
    start = time.time()
    naive_results = 0
    for i in range(num_files):
        file_path = python_files[i]
        file_eid = file_path.lower().replace("/", "-").replace("\\", "-").replace(".", "-").replace("_", "-").rstrip("-")
        for mod in imports_by_file[i]:
            result = find_import_target_naive(mod, file_eid, python_files)
            if result:
                naive_results += 1
    naive_time = time.time() - start
    
    # Benchmark optimized approach
    # Precompute lookup dictionary
    lookup_dict = {}
    for path in python_files:
        module = path.replace("/", ".").replace("\\", ".").removesuffix(".py")
        eid = path.lower().replace("/", "-").replace("\\", "-").replace(".", "-").replace("_", "-").rstrip("-")
        # Store both full module and last part
        lookup_dict[module] = eid
        lookup_dict[module.split(".")[-1]] = eid
    
    start = time.time()
    optimized_results = 0
    for i in range(num_files):
        file_path = python_files[i]
        file_eid = file_path.lower().replace("/", "-").replace("\\", "-").replace(".", "-").replace("_", "-").rstrip("-")
        for mod in imports_by_file[i]:
            result = find_import_target_optimized(mod, lookup_dict, file_eid)
            if result:
                optimized_results += 1
    optimized_time = time.time() - start
    
    print(f"Files: {num_files}, Imports per file: {imports_per_file}")
    print(f"Naive: {naive_time:.4f}s, found {naive_results} matches")
    print(f"Optimized: {optimized_time:.4f}s, found {optimized_results} matches")
    print(f"Speedup: {naive_time/optimized_time:.2f}x")
    
    return naive_time, optimized_time

if __name__ == "__main__":
    print("Benchmarking import matching performance")
    print("=" * 60)
    
    sizes = [10, 50, 100, 200]
    results = []
    
    for size in sizes:
        print(f"\nTesting with {size} files:")
        naive, optimized = benchmark_import_matching(size, 5)
        results.append((size, naive, optimized))
    
    print("\n" + "=" * 60)
    print("Summary:")
    for size, naive, optimized in results:
        print(f"{size:4d} files: {naive:7.4f}s -> {optimized:7.4f}s ({naive/optimized:5.1f}x speedup)")