#!/usr/bin/env python3
"""Final performance benchmark showing optimization results."""

import time
import random
from henchman.knowledge.scanner import (
    _build_module_lookup,
    _find_import_target,
    _find_import_target_optimized,
    _path_to_entity_id,
    _path_to_module,
)


def run_comprehensive_benchmark() -> None:
    """Run comprehensive benchmark showing scaling."""
    print("Scanner Performance Optimization Results")
    print("=" * 70)
    print("\nOptimization: O(n²) → O(1) import matching via precomputed lookup")
    print("\n" + "=" * 70)
    
    test_sizes = [10, 50, 100, 200, 500]
    results = []
    
    for num_files in test_sizes:
        print(f"\nTesting with {num_files} files:")
        
        # Generate test data
        python_files = []
        for i in range(num_files):
            depth = random.randint(1, 4)
            parts = [f"pkg_{j}" for j in range(depth)]
            parts.append(f"module_{i}")
            path = "/".join(parts) + ".py"
            python_files.append(path)
        
        # Generate imports (5 per file)
        test_imports = []
        for i in range(num_files):
            file_path = python_files[i]
            file_eid = _path_to_entity_id(file_path)
            
            for _ in range(5):  # 5 imports per file
                target_idx = random.randint(0, num_files - 1)
                target_path = python_files[target_idx]
                target_module = _path_to_module(target_path)
                
                # Use either full module or last part
                if random.random() > 0.5:
                    mod = target_module
                else:
                    mod = target_module.split(".")[-1]
                
                test_imports.append((mod, file_eid))
        
        # Benchmark naive
        start = time.time()
        for mod, file_eid in test_imports:
            _find_import_target(mod, file_eid, python_files)
        naive_time = time.time() - start
        
        # Benchmark optimized
        lookup = _build_module_lookup(python_files)
        start = time.time()
        for mod, file_eid in test_imports:
            _find_import_target_optimized(mod, file_eid, lookup)
        optimized_time = time.time() - start
        
        speedup = naive_time / optimized_time if optimized_time > 0 else float('inf')
        results.append((num_files, naive_time, optimized_time, speedup))
        
        print(f"  Import operations: {len(test_imports)}")
        print(f"  Naive time: {naive_time:.6f}s")
        print(f"  Optimized time: {optimized_time:.6f}s")
        print(f"  Speedup: {speedup:.1f}x")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Files':>6} {'Naive (s)':>12} {'Optimized (s)':>14} {'Speedup':>10}")
    print("-" * 70)
    
    for num_files, naive, optimized, speedup in results:
        print(f"{num_files:6d} {naive:12.6f} {optimized:14.6f} {speedup:10.1f}x")
    
    # Calculate complexity improvement
    print("\n" + "=" * 70)
    print("COMPLEXITY ANALYSIS")
    print("=" * 70)
    print("Original algorithm: O(n² × m)")
    print("  where n = number of files, m = average imports per file")
    print("\nOptimized algorithm: O(n + n × m) = O(n × m)")
    print("  - O(n) to build lookup table")
    print("  - O(1) per import lookup")
    print("\nFor 200 files with 5 imports each:")
    print(f"  - Original: O({200}² × 5) = O(200,000) operations")
    print(f"  - Optimized: O({200} × 5) = O(1,000) operations")
    print(f"  - Theoretical improvement: 200x")
    print(f"  - Actual measured: {results[3][3]:.1f}x")


if __name__ == "__main__":
    run_comprehensive_benchmark()